from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends, UploadFile, File, BackgroundTasks
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
import uuid
from datetime import datetime, timezone, timedelta
import httpx
import random
import string
import aiofiles
import asyncio

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
PAYMENT_THRESHOLD = 200 * 1024 * 1024  # 200MB
SUPPORTED_EXTENSIONS = ['mp4', 'mkv', 'avi', 'mov', 'mpeg', 'ogv', 'webm']
OUTPUT_EXPIRY_DAYS = 7
UPLOAD_DIR = Path("/tmp/video_uploads")
OUTPUT_DIR = Path("/tmp/video_outputs")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# ============== MODELS ==============

class UserBase(BaseModel):
    user_id: str
    email: str
    name: str
    picture: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Video(BaseModel):
    video_id: str = Field(default_factory=lambda: f"vid_{uuid.uuid4().hex[:12]}")
    user_id: str
    filename: str
    size_bytes: int
    extension: str
    object_key: str
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payment_required: bool = False
    payment_completed: bool = False

class Job(BaseModel):
    job_id: str = Field(default_factory=lambda: f"job_{uuid.uuid4().hex[:12]}")
    user_id: str
    video_id: str
    prompt_text: str
    status: str = "queued"  # queued, processing, done, failed, expired
    output_key: Optional[str] = None
    output_expires_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None

class Payment(BaseModel):
    payment_id: str = Field(default_factory=lambda: f"pay_{uuid.uuid4().hex[:12]}")
    user_id: str
    video_id: str
    amount: float
    currency: str = "INR"
    mode: str  # one_time or subscription
    status: str = "pending"  # pending, completed, failed
    razorpay_order_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Subscription(BaseModel):
    subscription_id: str = Field(default_factory=lambda: f"sub_{uuid.uuid4().hex[:12]}")
    user_id: str
    plan: str  # monthly, annual
    quota_bytes: int
    used_bytes: int = 0
    status: str = "active"  # active, cancelled, expired
    razorpay_subscription_id: Optional[str] = None
    starts_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = None

class DailyMetric(BaseModel):
    date: str  # YYYY-MM-DD
    visitors: int = 0
    videos_processed: int = 0

class OTPRecord(BaseModel):
    email: str
    otp: str
    expires_at: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# ============== REQUEST/RESPONSE MODELS ==============

class OTPRequestInput(BaseModel):
    email: EmailStr

class OTPVerifyInput(BaseModel):
    email: EmailStr
    otp: str

class UploadInitInput(BaseModel):
    filename: str
    size_bytes: int
    ext: str

class UploadInitResponse(BaseModel):
    presigned_url: str
    object_key: str
    requires_payment: bool
    quote: Optional[dict] = None

class UploadCompleteInput(BaseModel):
    object_key: str
    size_bytes: int

class BillingQuoteInput(BaseModel):
    size_bytes: int
    mode: str  # one_time or subscription

class BillingCheckoutInput(BaseModel):
    video_id: str
    mode: str  # one_time or subscription
    plan: Optional[str] = None  # monthly or annual for subscription

class JobCreateInput(BaseModel):
    video_id: str
    prompt_text: str = Field(max_length=1000)

class MetricsSummary(BaseModel):
    lifetime_visitors: int
    lifetime_videos_processed: int
    today_visitors: int
    today_videos_processed: int

# ============== AUTH HELPERS ==============

async def get_current_user(request: Request) -> dict:
    """Get current user from session token (cookie or header)"""
    session_token = request.cookies.get("session_token")
    if not session_token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            session_token = auth_header.split(" ")[1]
    
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    session = await db.user_sessions.find_one({"session_token": session_token}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
    
    expires_at = session.get("expires_at")
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired")
    
    user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user

async def get_optional_user(request: Request) -> Optional[dict]:
    """Get current user if authenticated, None otherwise"""
    try:
        return await get_current_user(request)
    except HTTPException:
        return None

# ============== AUTH ENDPOINTS ==============

@api_router.post("/auth/session")
async def create_session(request: Request, response: Response):
    """Exchange session_id for session_token (Emergent Auth)"""
    body = await request.json()
    session_id = body.get("session_id")
    
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")
    
    # Call Emergent Auth to get user data
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data",
            headers={"X-Session-ID": session_id}
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid session_id")
        user_data = resp.json()
    
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    email = user_data.get("email")
    name = user_data.get("name", "")
    picture = user_data.get("picture", "")
    session_token = user_data.get("session_token")
    
    # Check if user exists
    existing_user = await db.users.find_one({"email": email}, {"_id": 0})
    if existing_user:
        user_id = existing_user["user_id"]
    else:
        # Create new user
        await db.users.insert_one({
            "user_id": user_id,
            "email": email,
            "name": name,
            "picture": picture,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    
    # Create session
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    await db.user_sessions.insert_one({
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": expires_at.isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    # Set cookie
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=False,          # local dev
        samesite="lax",        # local dev
        #secure=True,
        #samesite="none",
        path="/",
        max_age=7 * 24 * 60 * 60
    )
    
    return {"user_id": user_id, "email": email, "name": name, "picture": picture}

@api_router.get("/auth/me")
async def get_me(user: dict = Depends(get_current_user)):
    """Get current authenticated user"""
    return user

@api_router.post("/auth/logout")
async def logout(request: Request, response: Response):
    """Logout user"""
    session_token = request.cookies.get("session_token")
    if session_token:
        await db.user_sessions.delete_one({"session_token": session_token})
    response.delete_cookie("session_token", path="/")
    return {"message": "Logged out"}

@api_router.post("/auth/otp/request")
async def request_otp(input: OTPRequestInput):
    """Request OTP for email login (MOCKED - OTP always 123456)"""
    otp = "123456"  # MOCKED: In production, generate random OTP
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
    
    # Store OTP
    await db.otps.delete_many({"email": input.email})
    await db.otps.insert_one({
        "email": input.email,
        "otp": otp,
        "expires_at": expires_at.isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    # MOCKED: In production, send email here
    logger.info(f"OTP for {input.email}: {otp} (MOCKED)")
    
    return {"message": "OTP sent to email", "mocked_otp": otp}

@api_router.post("/auth/otp/verify")
async def verify_otp(input: OTPVerifyInput, response: Response):
    """Verify OTP and create session"""
    otp_record = await db.otps.find_one({"email": input.email}, {"_id": 0})
    if not otp_record:
        raise HTTPException(status_code=400, detail="No OTP found for this email")
    
    expires_at = datetime.fromisoformat(otp_record["expires_at"])
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="OTP expired")
    
    if otp_record["otp"] != input.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    
    # Delete used OTP
    await db.otps.delete_one({"email": input.email})
    
    # Create or get user
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    existing_user = await db.users.find_one({"email": input.email}, {"_id": 0})
    if existing_user:
        user_id = existing_user["user_id"]
    else:
        await db.users.insert_one({
            "user_id": user_id,
            "email": input.email,
            "name": input.email.split("@")[0],
            "picture": None,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    
    # Create session
    session_token = f"sess_{uuid.uuid4().hex}"
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    await db.user_sessions.insert_one({
        "user_id": user_id,
        "session_token": session_token,
        "expires_at": expires_at.isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    # Set cookie
    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="none",
        path="/",
        max_age=7 * 24 * 60 * 60
    )
    
    user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
    return user

# ============== UPLOAD ENDPOINTS ==============

@api_router.post("/uploads/init", response_model=UploadInitResponse)
async def init_upload(input: UploadInitInput, request: Request, user: dict = Depends(get_current_user)):
    """Initialize upload and get presigned URL"""
    ext = input.ext.lower().lstrip('.')
    
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported extension. Supported: {', '.join(SUPPORTED_EXTENSIONS)}")
    
    if input.size_bytes > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Unable to process files of this size at the moment.")
    
    object_key = f"uploads/{user['user_id']}/{uuid.uuid4().hex}.{ext}"
    requires_payment = input.size_bytes > PAYMENT_THRESHOLD
    
    # MOCKED: Generate presigned URL (in production, use DigitalOcean Spaces)
    # Use the request's base URL to ensure correct domain
    backend_url = str(request.base_url).rstrip('/')
    if '/api/' in backend_url:
        backend_url = backend_url.split('/api/')[0]
    # Ensure HTTPS in production
    if 'preview.emergentagent.com' in backend_url:
        backend_url = backend_url.replace('http://', 'https://')
    presigned_url = f"{backend_url}/api/uploads/presigned/{object_key}"
    
    quote = None
    if requires_payment:
        quote = calculate_quote(input.size_bytes, "one_time")
    
    return UploadInitResponse(
        presigned_url=presigned_url,
        object_key=object_key,
        requires_payment=requires_payment,
        quote=quote
    )

@api_router.put("/uploads/presigned/{object_key:path}")
async def presigned_upload(object_key: str, request: Request):
    """MOCKED presigned upload endpoint"""
    file_path = UPLOAD_DIR / object_key.replace("/", "_")
    
    async with aiofiles.open(file_path, 'wb') as f:
        async for chunk in request.stream():
            await f.write(chunk)
    
    return {"message": "Upload successful", "object_key": object_key}

@api_router.post("/uploads/complete")
async def complete_upload(input: UploadCompleteInput, user: dict = Depends(get_current_user)):
    """Complete upload and create video record"""
    video_id = f"vid_{uuid.uuid4().hex[:12]}"
    ext = input.object_key.split('.')[-1]
    
    video = {
        "video_id": video_id,
        "user_id": user["user_id"],
        "filename": input.object_key.split('/')[-1],
        "size_bytes": input.size_bytes,
        "extension": ext,
        "object_key": input.object_key,
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "payment_required": input.size_bytes > PAYMENT_THRESHOLD,
        "payment_completed": input.size_bytes <= PAYMENT_THRESHOLD
    }
    
    await db.videos.insert_one(video)
    
    return {"video_id": video_id, "payment_required": video["payment_required"]}

# ============== BILLING ENDPOINTS ==============

def calculate_quote(size_bytes: int, mode: str) -> dict:
    """Calculate pricing based on size and mode"""
    size_mb = size_bytes / (1024 * 1024)
    
    if mode == "one_time":
        # Tier pricing
        if size_mb <= 500:
            amount = 49
        elif size_mb <= 1000:
            amount = 99
        else:
            amount = 149
        return {"amount": amount, "currency": "INR", "mode": "one_time"}
    else:
        # Subscription pricing
        return {
            "monthly": {"amount": 299, "currency": "INR", "quota_gb": 10},
            "annual": {"amount": 2499, "currency": "INR", "quota_gb": 150}
        }

@api_router.post("/billing/quote")
async def get_quote(input: BillingQuoteInput, user: dict = Depends(get_current_user)):
    """Get pricing quote"""
    return calculate_quote(input.size_bytes, input.mode)

@api_router.post("/billing/checkout")
async def create_checkout(input: BillingCheckoutInput, user: dict = Depends(get_current_user)):
    """Create Razorpay checkout (MOCKED)"""
    video = await db.videos.find_one({"video_id": input.video_id, "user_id": user["user_id"]}, {"_id": 0})
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    quote = calculate_quote(video["size_bytes"], input.mode)
    
    if input.mode == "one_time":
        # MOCKED: Create Razorpay order
        razorpay_order_id = f"order_{uuid.uuid4().hex[:12]}"
        payment = {
            "payment_id": f"pay_{uuid.uuid4().hex[:12]}",
            "user_id": user["user_id"],
            "video_id": input.video_id,
            "amount": quote["amount"],
            "currency": quote["currency"],
            "mode": "one_time",
            "status": "pending",
            "razorpay_order_id": razorpay_order_id,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.payments.insert_one(payment)
        
        return {
            "order_id": razorpay_order_id,
            "amount": quote["amount"] * 100,  # Razorpay expects paise
            "currency": quote["currency"],
            "key_id": "rzp_test_mocked",  # MOCKED
            "mocked": True
        }
    else:
        # MOCKED: Create subscription
        plan_quote = quote.get(input.plan, quote["monthly"])
        razorpay_subscription_id = f"sub_{uuid.uuid4().hex[:12]}"
        
        return {
            "subscription_id": razorpay_subscription_id,
            "amount": plan_quote["amount"] * 100,
            "currency": plan_quote["currency"],
            "key_id": "rzp_test_mocked",  # MOCKED
            "plan": input.plan,
            "mocked": True
        }

@api_router.post("/billing/webhook")
async def billing_webhook(request: Request):
    """Handle Razorpay webhook (MOCKED)"""
    body = await request.json()
    
    # MOCKED: In production, verify signature
    event = body.get("event")
    
    if event == "payment.captured":
        order_id = body.get("payload", {}).get("payment", {}).get("entity", {}).get("order_id")
        if order_id:
            payment = await db.payments.find_one({"razorpay_order_id": order_id}, {"_id": 0})
            if payment:
                await db.payments.update_one(
                    {"razorpay_order_id": order_id},
                    {"$set": {"status": "completed"}}
                )
                await db.videos.update_one(
                    {"video_id": payment["video_id"]},
                    {"$set": {"payment_completed": True}}
                )
    
    return {"status": "ok"}

@api_router.post("/billing/mock-complete")
async def mock_complete_payment(video_id: str, user: dict = Depends(get_current_user)):
    """MOCKED: Complete payment for testing"""
    result = await db.videos.update_one(
        {"video_id": video_id, "user_id": user["user_id"]},
        {"$set": {"payment_completed": True}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Video not found")
    return {"message": "Payment completed (mocked)", "video_id": video_id}

# ============== JOB ENDPOINTS ==============

def parse_prompt(prompt_text: str) -> dict:
    """Parse prompt into segments and order"""
    result = {
        "segments": [],
        "order": [],
        "output_format": "mp4",
        "quality": "medium"
    }
    
    lines = prompt_text.strip().split('.')
    for line in lines:
        line = line.strip()
        if line.lower().startswith("keep:"):
            # Parse segments
            segments_str = line[5:].strip()
            parts = [p.strip() for p in segments_str.split(',')]
            for i, part in enumerate(parts):
                if '-' in part:
                    times = part.split('-')
                    if len(times) == 2:
                        result["segments"].append({
                            "index": i + 1,
                            "start": times[0].strip(),
                            "end": times[1].strip()
                        })
        elif line.lower().startswith("order:"):
            order_str = line[6:].strip()
            try:
                result["order"] = [int(x.strip()) for x in order_str.split(',')]
            except:
                pass
        elif line.lower().startswith("output:"):
            result["output_format"] = line[7:].strip().lower()
        elif line.lower().startswith("quality:"):
            result["quality"] = line[8:].strip().lower()
    
    # Default order if not specified
    if not result["order"] and result["segments"]:
        result["order"] = [s["index"] for s in result["segments"]]
    
    return result

async def process_job(job_id: str):
    """MOCKED: Process video job"""
    await asyncio.sleep(5)  # Simulate processing
    
    job = await db.jobs.find_one({"job_id": job_id}, {"_id": 0})
    if not job:
        return
    
    # MOCKED: Update job as done
    output_key = f"outputs/{job['user_id']}/{uuid.uuid4().hex}.mp4"
    await db.jobs.update_one(
        {"job_id": job_id},
        {"$set": {
            "status": "done",
            "output_key": output_key,
            "output_expires_at": (datetime.now(timezone.utc) + timedelta(days=OUTPUT_EXPIRY_DAYS)).isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    # Increment today's videos processed
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    await db.metrics.update_one(
        {"date": today},
        {"$inc": {"videos_processed": 1}},
        upsert=True
    )
    
    logger.info(f"Job {job_id} completed (MOCKED)")

@api_router.post("/jobs")
async def create_job(input: JobCreateInput, background_tasks: BackgroundTasks, user: dict = Depends(get_current_user)):
    """Create a new video editing job"""
    video = await db.videos.find_one({"video_id": input.video_id, "user_id": user["user_id"]}, {"_id": 0})
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    
    if video.get("payment_required") and not video.get("payment_completed"):
        raise HTTPException(status_code=402, detail="Payment required")
    
    # Check active subscription
    subscription = await db.subscriptions.find_one(
        {"user_id": user["user_id"], "status": "active"},
        {"_id": 0}
    )
    
    if len(input.prompt_text) > 1000:
        raise HTTPException(status_code=400, detail="Prompt exceeds 1000 characters")
    
    # Parse prompt
    parsed = parse_prompt(input.prompt_text)
    
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    job = {
        "job_id": job_id,
        "user_id": user["user_id"],
        "video_id": input.video_id,
        "prompt_text": input.prompt_text,
        "parsed_prompt": parsed,
        "status": "queued",
        "output_key": None,
        "output_expires_at": None,
        "error_message": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None
    }
    
    await db.jobs.insert_one(job)
    
    # Start processing in background
    background_tasks.add_task(process_job, job_id)
    
    return {"job_id": job_id, "status": "queued"}

@api_router.get("/jobs")
async def list_jobs(user: dict = Depends(get_current_user)):
    """List user's recent jobs"""
    jobs = await db.jobs.find(
        {"user_id": user["user_id"]},
        {"_id": 0}
    ).sort("created_at", -1).limit(20).to_list(20)
    return jobs

@api_router.get("/jobs/{job_id}")
async def get_job(job_id: str, user: dict = Depends(get_current_user)):
    """Get job details"""
    job = await db.jobs.find_one({"job_id": job_id, "user_id": user["user_id"]}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@api_router.get("/jobs/{job_id}/download")
async def get_download_url(job_id: str, user: dict = Depends(get_current_user)):
    """Get signed download URL for completed job"""
    job = await db.jobs.find_one({"job_id": job_id, "user_id": user["user_id"]}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job["status"] != "done":
        raise HTTPException(status_code=400, detail="Job not completed")
    
    expires_at = job.get("output_expires_at")
    if expires_at:
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            raise HTTPException(status_code=410, detail="Download link expired")
    
    # MOCKED: Return download URL
    return {"download_url": f"/api/downloads/{job['output_key']}", "expires_at": expires_at}

# ============== METRICS ENDPOINTS ==============

@api_router.get("/metrics/summary", response_model=MetricsSummary)
async def get_metrics_summary():
    """Get metrics summary"""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    # Get all metrics
    all_metrics = await db.metrics.find({}, {"_id": 0}).to_list(1000)
    
    lifetime_visitors = sum(m.get("visitors", 0) for m in all_metrics)
    lifetime_videos = sum(m.get("videos_processed", 0) for m in all_metrics)
    
    today_metric = next((m for m in all_metrics if m.get("date") == today), {})
    
    return MetricsSummary(
        lifetime_visitors=lifetime_visitors or 1234,  # Default demo values
        lifetime_videos_processed=lifetime_videos or 567,
        today_visitors=today_metric.get("visitors", 42),
        today_videos_processed=today_metric.get("videos_processed", 12)
    )

# ============== VISITOR TRACKING MIDDLEWARE ==============

@app.middleware("http")
async def track_visitors(request: Request, call_next):
    """Track unique visitors per day"""
    response = await call_next(request)
    
    # Only track page requests, not API calls
    if not request.url.path.startswith("/api"):
        visitor_id = request.cookies.get("visitor_id")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        if not visitor_id:
            visitor_id = f"v_{uuid.uuid4().hex[:12]}"
            response.set_cookie("visitor_id", visitor_id, max_age=24*60*60)
        
        # Check if already counted today
        visitor_key = f"{visitor_id}_{today}"
        try:
            existing = await db.visitor_tracking.find_one({"key": visitor_key})
            if not existing:
                await db.visitor_tracking.insert_one({"key": visitor_key, "date": today})
                await db.metrics.update_one(
                    {"date": today},
                    {"$inc": {"visitors": 1}},
                    upsert=True
                )
        except Exception as e:
            logger.warning(f"Visitor tracking skipped: {e}")

    
    return response

# ============== ROOT ENDPOINTS ==============

@api_router.get("/")
async def root():
    return {"message": "Video Editor API", "version": "1.0.0"}

@api_router.get("/health")
async def health():
    return {"status": "healthy"}

# Include router
app.include_router(api_router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
