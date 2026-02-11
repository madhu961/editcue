# EditCue - Video Editing Tool MVP

## Original Problem Statement
Build a production-ready MVP for a 2–3 page website video editing tool with:
- Landing page (public) at /
- Tool page (login required) at /tool  
- Help/FAQ page at /help
- Google OAuth + Email OTP authentication
- Video upload with size validation (>2GB reject, >200MB requires payment)
- Prompt-based video editing with FFmpeg
- Job status tracking and download links (7-day expiry)
- Metrics display (lifetime and today stats)

## Architecture

### Stack
- **Frontend**: React 19 + Tailwind CSS + Shadcn UI
- **Backend**: FastAPI + MongoDB (Motor async driver)
- **Auth**: Emergent Google Auth + Email OTP (mocked SMTP)
- **Storage**: Mocked DigitalOcean Spaces (local file storage)
- **Payment**: Mocked Razorpay integration
- **Jobs**: Background tasks with FastAPI BackgroundTasks

### Key Files
```
/app/backend/
  server.py          # All API endpoints
/app/frontend/src/
  App.js             # Main app with routing & auth context
  pages/
    Landing.jsx      # Public landing page
    Tool.jsx         # Protected editor page
    Help.jsx         # Help/FAQ page
  components/
    Navbar.jsx       # Glass morphism navbar
    AuthCallback.jsx # Emergent Auth callback handler
    Stepper.jsx      # Upload wizard stepper
    JobTracker.jsx   # Job status display
    MetricsDisplay.jsx # Analytics metrics
    UploadScene.jsx  # CSS animation during upload
```

## User Personas
1. **Casual Content Creator**: Wants quick edits without learning complex software
2. **YouTuber**: Needs to trim and reorder clips fast
3. **Social Media Manager**: Bulk editing for multiple platforms

## Core Requirements (Static)
- [x] Landing page with hero, features, how-it-works
- [x] Google OAuth via Emergent Auth
- [x] Email OTP login (mocked, OTP always 123456)
- [x] Protected /tool route
- [x] Video upload with file validation
- [x] Size-based payment requirement (>200MB)
- [x] Prompt parsing (Keep, Order, Output, Quality)
- [x] Job creation and status tracking
- [x] Background job processing (mocked)
- [x] Download link generation
- [x] Metrics display
- [x] Help page with FAQ accordion

## What's Been Implemented (Feb 11, 2026)

### Backend APIs
- `POST /api/auth/session` - Emergent Auth session exchange
- `GET /api/auth/me` - Get current user
- `POST /api/auth/logout` - Logout user
- `POST /api/auth/otp/request` - Request email OTP
- `POST /api/auth/otp/verify` - Verify OTP and create session
- `POST /api/uploads/init` - Initialize upload, get presigned URL
- `PUT /api/uploads/presigned/{key}` - Upload file (mocked)
- `POST /api/uploads/complete` - Complete upload, create Video record
- `POST /api/billing/quote` - Get pricing quote
- `POST /api/billing/checkout` - Create payment (mocked)
- `POST /api/billing/mock-complete` - Complete payment for testing
- `POST /api/jobs` - Create editing job
- `GET /api/jobs` - List user's jobs
- `GET /api/jobs/{id}` - Get job details
- `GET /api/jobs/{id}/download` - Get download URL
- `GET /api/metrics/summary` - Get analytics summary

### Frontend Pages
- Landing (/) - Hero, features grid, how-it-works, CTA
- Tool (/tool) - Stepper, upload dropzone, job tracker, metrics
- Help (/help) - Syntax reference, FAQ accordion

### Design
- Dark theme with Acid Lime (#CCFF00) primary color
- Space Grotesk + DM Sans fonts
- Glass morphism navbar
- Noise texture background
- Bento grid layout for features

## Mocked Integrations
- **DigitalOcean Spaces**: Uses local /tmp storage
- **Razorpay Payment**: Mock checkout, mock-complete endpoint
- **Email Service**: OTP always returns 123456
- **FFmpeg Processing**: 5-second delay then marks job done

## Prioritized Backlog

### P0 - Critical (Before Production)
- [ ] Real DigitalOcean Spaces integration
- [ ] Real Razorpay payment integration
- [ ] Real FFmpeg video processing in Celery worker
- [ ] Email service for OTP and notifications

### P1 - High Priority
- [ ] Subscription plans (monthly/annual)
- [ ] Video preview before processing
- [ ] Real-time job progress updates (WebSockets)
- [ ] File deletion after 7-day expiry (scheduled task)

### P2 - Nice to Have
- [ ] Multiple video upload queue
- [ ] Video thumbnails
- [ ] User dashboard with history
- [ ] Advanced prompt syntax (transitions, overlays)
- [ ] React Three Fiber 3D animation (needs React 19 compatibility)

## Next Tasks
1. Integrate real DigitalOcean Spaces for file storage
2. Set up Razorpay live payment with webhooks
3. Implement Celery worker with FFmpeg for actual video processing
4. Add real email service (Resend or SendGrid)
5. Deploy to production with Kubernetes manifests
