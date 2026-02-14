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
import secrets
import hashlib
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

PAY_FIRST_MODE = os.getenv("PAY_FIRST_MODE","1")=="1"


def hash_otp(email: str, otp: str) -> str:
    return hashlib.sha256(f"{email}:{otp}".encode()).hexdigest()

async def send_otp_email(to_email: str, otp: str):
    message = Mail(
        from_email=os.environ["FROM_EMAIL"],
        to_emails=to_email,
        subject="Your EditCue login code",
        html_content=f"""
        <div style="font-family:Arial">
          <h2>Your EditCue OTP</h2>
          <p>Use this code to log in:</p>
          <div style="font-size:28px;font-weight:800;letter-spacing:4px">{otp}</div>
          <p>This code expires in 10 minutes.</p>
        </div>
        """
    )
    sg = SendGridAPIClient(os.environ["SENDGRID_API_KEY"])
    sg.send(message)

ANTIDEO_API_KEY = os.getenv("ANTIDEO_API_KEY", "")
ENABLE_ANTIDEO_EMAIL_CHECK = os.getenv("ENABLE_ANTIDEO_EMAIL_CHECK", "1") == "1"

async def antideo_email_health(email: str) -> dict:
    """
    Calls Antideo email health endpoint:
    GET https://api.antideo.com/email/{email}
    API key must be provided in request header. :contentReference[oaicite:1]{index=1}
    """
    if not ANTIDEO_API_KEY:
        return {"_skip": True, "_reason": "ANTIDEO_API_KEY not set"}

    url = f"https://api.antideo.com/email/{email}"
    headers = {
        # Antideo docs: "pass the API Key in the header" (header name isn't shown in docs)
        # Using common variants to be safe:
        "APIKEY": ANTIDEO_API_KEY,
        "apikey": ANTIDEO_API_KEY,
        "X-API-KEY": ANTIDEO_API_KEY,
    }

    async with httpx.AsyncClient(timeout=6.0) as client:
        r = await client.get(url, headers=headers)
        # Antideo uses standard error codes like 401 if key is wrong. :contentReference[oaicite:2]{index=2}
        r.raise_for_status()
        return r.json()

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
    video_id: Optional[str] = None

class UploadInitResponse(BaseModel):
    presigned_url: str
    object_key: str
    requires_payment: bool
    quote: Optional[dict] = None

class UploadCompleteInput(BaseModel):
    video_id: str
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
    # Antideo email health check (before OTP)
    if ENABLE_ANTIDEO_EMAIL_CHECK:
        try:
            info = await antideo_email_health(input.email)

            # If Antideo is skipped because key not set, don't block logins
            if not info.get("_skip"):
                disposable = bool(info.get("disposable"))
                spam = info.get("spam")
                scam = info.get("scam")

                # Recommended policy:
                # - Block disposable
                # - Block if spam/scam has a report object (not False)
                if disposable:
                    raise HTTPException(status_code=400, detail="Disposable emails are not allowed.")
                if spam and spam is not False:
                    raise HTTPException(status_code=400, detail="Email flagged as spam risk. Please use another email.")
                if scam and scam is not False:
                    raise HTTPException(status_code=400, detail="Email flagged as scam risk. Please use another email.")
        except HTTPException:
            raise
        except Exception as e:
            # Fail-open: do not block OTP if Antideo is down
            logging.warning(f"Antideo email check failed: {e}")
    otp = f"{secrets.randbelow(10**6):06d}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    await db.otps.delete_many({"email": input.email})
    await db.otps.insert_one({
        "email": input.email,
        "otp_hash": hash_otp(input.email, otp),
        "expires_at": expires_at.isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    await send_otp_email(input.email, otp)

    return {"message": "OTP sent to email"}


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
    
    if otp_record["otp_hash"] != hash_otp(input.email, input.otp):
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
import boto3
from botocore.client import Config

SPACES_REGION = os.environ.get("SPACES_REGION")
SPACES_BUCKET = os.environ.get("SPACES_BUCKET")
SPACES_ENDPOINT = os.environ.get("SPACES_ENDPOINT")
SPACES_PUBLIC_BASE = os.environ.get("SPACES_PUBLIC_BASE")

session = boto3.session.Session()
s3 = boto3.client(
    "s3",
    region_name=SPACES_REGION,
    endpoint_url=f"https://{SPACES_REGION}.digitaloceanspaces.com",
    aws_access_key_id=os.environ.get("SPACES_KEY"),
    aws_secret_access_key=os.environ.get("SPACES_SECRET"),
    config=Config(
        signature_version="s3v4",
        s3={"addressing_style": "virtual"}  # 🔥 THIS IS IMPORTANT
    ),
)


def presign_put(bucket: str, key: str, content_type: str, expires=3600):
    return s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": bucket, "Key": key, "ContentType": content_type},
        ExpiresIn=expires,
    )

class UploadReserveInput(BaseModel):
    filename: str
    size_bytes: int
    ext: str

@api_router.post("/uploads/reserve")
async def reserve_upload(input: UploadReserveInput, user: dict = Depends(get_current_user)):
    ext = input.ext.lower().lstrip(".")
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported extension")
    if input.size_bytes > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="Unable to process files of this size at the moment.")

    video_id = f"vid_{uuid.uuid4().hex[:12]}"
    requires_payment = input.size_bytes > PAYMENT_THRESHOLD
    quote = calculate_quote(input.size_bytes, "one_time") if requires_payment else None

    safe_name = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in input.filename)
    object_key = f"uploads/{user['user_id']}/{video_id}_{safe_name}"

    video = {
        "video_id": video_id,
        "user_id": user["user_id"],
        "filename": safe_name,
        "size_bytes": input.size_bytes,
        "extension": ext,
        "object_key": object_key,
        "uploaded_at": None,
        "upload_status": "reserved",           # NEW
        "payment_required": requires_payment,
        "payment_completed": (not requires_payment),
        "file_url": f"{SPACES_PUBLIC_BASE}/{object_key}" if SPACES_PUBLIC_BASE else None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    await db.videos.insert_one(video)

    return {
        "video_id": video_id,
        "object_key": object_key,
        "requires_payment": requires_payment,
        "quote": quote
    }


@api_router.post("/uploads/init", response_model=UploadInitResponse)
async def init_upload(input: UploadInitInput, request: Request, user: dict = Depends(get_current_user)):
    logger.info(f"[Init Upload Checking pay first mode {PAY_FIRST_MODE}")
    # If PAY_FIRST_MODE: require a reserved video_id
    if PAY_FIRST_MODE:
        if not input.video_id:
            raise HTTPException(status_code=400, detail="video_id required in pay-first mode")
        logger.info(f"[Init Upload Fetching video")
        video = await db.videos.find_one({"video_id": input.video_id, "user_id": user["user_id"]}, {"_id": 0})
        if not video:
            logger.info(f"[Init Upload Fetching video")
            raise HTTPException(status_code=404, detail="Video not found")
        logger.info(f"[Init Upload Fetched video {video}")
        # hard block upload until paid (only when payment is required)
        if video.get("payment_required") and not video.get("payment_completed"):
            quote = calculate_quote(video["size_bytes"], "one_time")
            return UploadInitResponse(
                presigned_url=None,
                object_key=video["object_key"],
                requires_payment=True,
                quote=quote
            )

        object_key = video["object_key"]
        size_bytes = video["size_bytes"]

    else:
        # Your current behaviour (pay-after allowed)
        ext = input.ext.lower().lstrip(".")
        if ext not in SUPPORTED_EXTENSIONS:
            raise HTTPException(status_code=400, detail="Unsupported extension")
        if input.size_bytes > MAX_FILE_SIZE:
            raise HTTPException(status_code=400, detail="Unable to process files of this size at the moment.")
        safe_name = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in input.filename)
        object_key = f"uploads/{user['user_id']}/{uuid.uuid4().hex}_{safe_name}"
        size_bytes = input.size_bytes

    presigned_url = s3.generate_presigned_url(
        ClientMethod="put_object",
        Params={"Bucket": SPACES_BUCKET, "Key": object_key},
        ExpiresIn=60 * 15,
    )

    requires_payment = size_bytes > PAYMENT_THRESHOLD
    quote = calculate_quote(size_bytes, "one_time") if requires_payment else None

    return UploadInitResponse(
        presigned_url=presigned_url,
        object_key=object_key,
        requires_payment=requires_payment,
        quote=quote
    )


@api_router.post("/uploads/complete")
async def complete_upload(input: UploadCompleteInput, user: dict = Depends(get_current_user)):

    # verify exists in Spaces
    try:
        s3.head_object(Bucket=SPACES_BUCKET, Key=input.object_key)
    except Exception:
        raise HTTPException(status_code=400, detail="Upload not found in storage. Please retry upload.")

    video = await db.videos.find_one({"video_id": input.video_id, "user_id": user["user_id"]})
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    # (Optional) in pay-first mode ensure key matches reserved
    if PAY_FIRST_MODE and video.get("object_key") != input.object_key:
        raise HTTPException(status_code=400, detail="object_key mismatch")

    await db.videos.update_one(
        {"video_id": input.video_id, "user_id": user["user_id"]},
        {"$set": {
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "upload_status": "uploaded",
            "size_bytes": input.size_bytes,
            "payment_required": input.size_bytes > PAYMENT_THRESHOLD,
            "payment_completed": video.get("payment_completed", False) or (input.size_bytes <= PAYMENT_THRESHOLD)
        }}
    )

    return {"video_id": input.video_id, "payment_required": input.size_bytes > PAYMENT_THRESHOLD}


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

import razorpay

client_rzp = razorpay.Client(auth=(os.environ["RAZORPAY_KEY_ID"], os.environ["RAZORPAY_KEY_SECRET"]))

@api_router.post("/billing/checkout")
async def create_checkout(input: BillingCheckoutInput, user: dict = Depends(get_current_user)):
    video = await db.videos.find_one({"video_id": input.video_id, "user_id": user["user_id"]})
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    if video.get("payment_completed"):
        return {"already_paid": True}

    quote = calculate_quote(video["size_bytes"], input.mode)

    if input.mode == "one_time":
        order = client_rzp.order.create({
            "amount": int(quote["amount"] * 100),  # paise
            "currency": "INR",
            "receipt": f"{input.video_id}",
            "notes": {"user_id": user["user_id"], "video_id": input.video_id}
        })

        await db.payments.insert_one({
            "user_id": user["user_id"],
            "video_id": input.video_id,
            "status": "pending",
            "razorpay_order_id": order["id"],
            "amount": quote["amount"],
            "currency": "INR",
            "created_at": datetime.now(timezone.utc).isoformat()
        })

        return {
            "order_id": order["id"],
            "amount": order["amount"],
            "currency": order["currency"],
            "key_id": os.environ["RAZORPAY_KEY_ID"]
        }

    raise HTTPException(status_code=400, detail="Unsupported mode")

import hmac, hashlib

def verify_razorpay_signature(body: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)

@api_router.post("/billing/webhook")
async def billing_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    if not verify_razorpay_signature(body, signature, os.environ["RAZORPAY_WEBHOOK_SECRET"]):
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()
    event = payload.get("event")

    if event == "payment.captured":
        order_id = payload["payload"]["payment"]["entity"]["order_id"]
        payment = await db.payments.find_one({"razorpay_order_id": order_id})
        if payment:
            await db.payments.update_one({"razorpay_order_id": order_id}, {"$set": {"status": "completed"}})
            await db.videos.update_one({"video_id": payment["video_id"]}, {"$set": {"payment_completed": True}})
    return {"status": "ok"}

class BillingVerifyInput(BaseModel):
    video_id: str
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str

@api_router.post("/billing/verify")
async def verify_payment(input: BillingVerifyInput, user: dict = Depends(get_current_user)):
    # 1) Ensure payment record exists and belongs to this user/video
    payment = await db.payments.find_one({
        "razorpay_order_id": input.razorpay_order_id,
        "user_id": user["user_id"],
        "video_id": input.video_id,
    })
    if not payment:
        raise HTTPException(status_code=404, detail="Payment record not found")

    if payment.get("status") == "completed":
        return {"status": "already_completed"}

    # 2) Verify signature (order_id|payment_id with key_secret)
    try:
        client_rzp.utility.verify_payment_signature({
            "razorpay_order_id": input.razorpay_order_id,
            "razorpay_payment_id": input.razorpay_payment_id,
            "razorpay_signature": input.razorpay_signature,
        })
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid payment signature")

    # 3) Optional but strong: confirm payment is captured and amount matches
    rp_payment = client_rzp.payment.fetch(input.razorpay_payment_id)
    if rp_payment.get("status") != "captured":
        raise HTTPException(status_code=400, detail=f"Payment not captured: {rp_payment.get('status')}")

    # amount is in paise
    expected_amount = int(payment["amount"] * 100)
    if int(rp_payment.get("amount", 0)) != expected_amount:
        raise HTTPException(status_code=400, detail="Amount mismatch")

    # 4) Mark completed
    await db.payments.update_one(
        {"razorpay_order_id": input.razorpay_order_id},
        {"$set": {"status": "completed", "razorpay_payment_id": input.razorpay_payment_id}}
    )
    await db.videos.update_one(
        {"video_id": input.video_id, "user_id": user["user_id"]},
        {"$set": {"payment_completed": True}}
    )

    return {"status": "ok", "video_id": input.video_id}


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
        result["order"] = [s["index"] for s in result["segments"]]
    
    return result

import subprocess
from botocore.exceptions import ClientError

def ts_to_seconds(ts: str) -> float:
    """
    Accepts:
      "SS", "MM:SS", "HH:MM:SS" (optionally with .ms)
    Returns seconds as float.
    """
    ts = ts.strip()
    parts = ts.split(":")
    if len(parts) == 1:
        return float(parts[0])
    if len(parts) == 2:
        mm, ss = parts
        return float(mm) * 60 + float(ss)
    if len(parts) == 3:
        hh, mm, ss = parts
        return float(hh) * 3600 + float(mm) * 60 + float(ss)
    raise ValueError(f"Invalid timestamp: {ts}")

def quality_to_crf(quality: str) -> int:
    q = (quality or "medium").lower()
    # lower CRF = higher quality / larger file
    return {"high": 20, "medium": 23, "low": 28}.get(q, 23)

async def head_with_retry(bucket: str, key: str, attempts: int = 6):
    delay = 0.4
    for _ in range(attempts):
        try:
            s3.head_object(Bucket=bucket, Key=key)
            return
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code")
            if code in ("404", "NoSuchKey", "NotFound"):
                await asyncio.sleep(delay)
                delay = min(delay * 2, 3.0)
                continue
            raise
    raise RuntimeError(f"Object not found after retries: {key}")

async def process_job(job_id: str):
    logger.info(f"[JOB {job_id}] start")

    input_path = None
    output_path = None

    try:
        job = await db.jobs.find_one({"job_id": job_id}, {"_id": 0})
        if not job:
            logger.error(f"[JOB {job_id}] not found")
            return

        await db.jobs.update_one({"job_id": job_id}, {"$set": {"status": "processing"}})
        logger.info(f"[JOB {job_id}] status=processing")

        video = await db.videos.find_one({"video_id": job["video_id"]}, {"_id": 0})
        if not video:
            raise RuntimeError("Video not found")

        input_key = video["object_key"]
        logger.info(f"[JOB {job_id}] input_key={input_key}")

        parsed = job.get("parsed_prompt") or {}
        segments = parsed.get("segments") or []
        order = parsed.get("order") or [s.get("index") for s in segments]
        out_fmt = (parsed.get("output_format") or "mp4").lower()
        crf = quality_to_crf(parsed.get("quality"))

        if not segments:
            raise RuntimeError("No segments found in prompt. Use: Keep: 00:00-00:10")

        # map index -> segment
        seg_map = {s["index"]: s for s in segments if "index" in s and "start" in s and "end" in s}

        ordered = []
        for idx in order:
            if idx in seg_map:
                ordered.append(seg_map[idx])

        if not ordered:
            raise RuntimeError("Segment order invalid / no segments matched")

        # local file paths
        input_ext = (video.get("extension") or "mp4").lower()
        input_path = UPLOAD_DIR / f"{job_id}_input.{input_ext}"
        output_path = OUTPUT_DIR / f"{job_id}_output.{out_fmt}"
        output_key = f"outputs/{job['user_id']}/{job_id}.{out_fmt}"

        logger.info(f"[JOB {job_id}] download to {input_path}")

        # ensure the object is readable (Spaces consistency / race)
        await head_with_retry(SPACES_BUCKET, input_key)

        # download from Spaces
        s3.download_file(SPACES_BUCKET, input_key, str(input_path))
        if not input_path.exists() or input_path.stat().st_size == 0:
            raise RuntimeError("Input download failed / empty file")

        logger.info(f"[JOB {job_id}] input size={input_path.stat().st_size}")

        # Build filter_complex:
        # [0:v]trim=start=..:end=..,setpts=PTS-STARTPTS[v0];
        # [0:a]atrim=start=..:end=..,asetpts=PTS-STARTPTS[a0];
        # ... concat=n=N:v=1:a=1[outv][outa]
        filter_parts = []
        concat_inputs = []
        for i, seg in enumerate(ordered):
            s = ts_to_seconds(seg["start"])
            e = ts_to_seconds(seg["end"])
            if e <= s:
                raise RuntimeError(f"Invalid segment: {seg['start']}-{seg['end']}")

            filter_parts.append(f"[0:v]trim=start={s}:end={e},setpts=PTS-STARTPTS[v{i}]")
            filter_parts.append(f"[0:a]atrim=start={s}:end={e},asetpts=PTS-STARTPTS[a{i}]")
            concat_inputs.append(f"[v{i}][a{i}]")

        filter_complex = ";".join(filter_parts) + ";" + "".join(concat_inputs) + f"concat=n={len(ordered)}:v=1:a=1[outv][outa]"
        logger.info(f"[JOB {job_id}] filter_complex={filter_complex}")

        # ffmpeg command (re-encode for accurate cuts)
        cmd = [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-filter_complex", filter_complex,
            "-map", "[outv]",
            "-map", "[outa]",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", str(crf),
            "-c:a", "aac",
            "-b:a", "128k",
            str(output_path)
        ]

        logger.info(f"[JOB {job_id}] run ffmpeg: {' '.join(cmd)}")

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            err = stderr.decode(errors="ignore")
            raise RuntimeError(f"ffmpeg failed: {err[:2000]}")

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError("Output not created / empty")

        logger.info(f"[JOB {job_id}] output size={output_path.stat().st_size}")

        # upload output
        logger.info(f"[JOB {job_id}] upload output_key={output_key}")
        s3.upload_file(str(output_path), SPACES_BUCKET, output_key)

        # verify output exists
        s3.head_object(Bucket=SPACES_BUCKET, Key=output_key)
        logger.info(f"[JOB {job_id}] output verified")

        await db.jobs.update_one(
            {"job_id": job_id},
            {"$set": {
                "status": "done",
                "output_key": output_key,
                "output_expires_at": (datetime.now(timezone.utc) + timedelta(days=OUTPUT_EXPIRY_DAYS)).isoformat(),
                "completed_at": datetime.now(timezone.utc).isoformat()
            }}
        )

        # metrics
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        await db.metrics.update_one({"date": today}, {"$inc": {"videos_processed": 1}}, upsert=True)

        logger.info(f"[JOB {job_id}] done")

    except Exception as e:
        logger.exception(f"[JOB {job_id}] failed: {e}")
        await db.jobs.update_one(
            {"job_id": job_id},
            {"$set": {
                "status": "failed",
                "error_message": str(e),
                "completed_at": datetime.now(timezone.utc).isoformat()
            }}
        )
    finally:
        # cleanup local files
        try:
            if input_path and input_path.exists():
                input_path.unlink()
            if output_path and output_path.exists():
                output_path.unlink()
        except Exception as ce:
            logger.warning(f"[JOB {job_id}] cleanup error: {ce}")



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
    job = await db.jobs.find_one({"job_id": job_id, "user_id": user["user_id"]}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["status"] != "done" or not job.get("output_key"):
        raise HTTPException(status_code=400, detail="Job not completed")

    # Ensure object exists in Spaces (prevents broken links)
    try:
        s3.head_object(Bucket=SPACES_BUCKET, Key=job["output_key"])
    except Exception:
        raise HTTPException(status_code=404, detail="Output file not found. Job may have failed to upload output.")

    # Presigned GET URL (valid for 30 mins)
    url = s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": SPACES_BUCKET, "Key": job["output_key"]},
        ExpiresIn=60 * 60 * 24 * 7
    )

    return {"download_url": url}

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
