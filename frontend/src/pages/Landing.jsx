import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth, API } from "@/App";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { InputOTP, InputOTPGroup, InputOTPSlot } from "@/components/ui/input-otp";
import { toast } from "sonner";
import axios from "axios";
import { 
  Scissors, 
  Zap, 
  DollarSign, 
  Clock, 
  ArrowRight, 
  Play,
  Sparkles,
  Mail
} from "lucide-react";

const Landing = () => {
  const { user, setUser } = useAuth();
  const navigate = useNavigate();
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [authMode, setAuthMode] = useState("google"); // google or otp
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [otpSent, setOtpSent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [emailError, setEmailError] = useState("");
  const isValidEmail = (v) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);
  // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
  const handleGoogleLogin = () => {
    const redirectUrl = window.location.origin + '/tool';
    window.location.href = `https://auth.emergentagent.com/?redirect=${encodeURIComponent(redirectUrl)}`;
  };

  const handleRequestOTP = async () => {
    if (!email) {
      toast.error("Please enter your email");
      return;
    }
    if (!isValidEmail(email)) {
      setEmailError("Invalid email format");
      toast.error("Invalid email format");
      return;
    }
    setLoading(true);
    try {
      const response = await axios.post(`${API}/auth/otp/request`, { email });
      setOtpSent(true);
      toast.success("OTP sent to your email");
      // Show mocked OTP in dev
      if (response.data.mocked_otp) {
        toast.info(`Dev Mode: OTP is ${response.data.mocked_otp}`);
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to send OTP");
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyOTP = async () => {
    if (otp.length !== 6) {
      toast.error("Please enter complete OTP");
      return;
    }
    
    setLoading(true);
    try {
      const response = await axios.post(
        `${API}/auth/otp/verify`, 
        { email, otp },
        { withCredentials: true }
      );
      setUser(response.data);
      setShowAuthModal(false);
      navigate("/tool");
      toast.success("Login successful!");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Invalid OTP");
    } finally {
      setLoading(false);
    }
  };

  // If user is logged in, show CTA to go to tool
  const handleGetStarted = () => {
    if (user) {
      navigate("/tool");
    } else {
      setShowAuthModal(true);
    }
  };

  const features = [
    {
      icon: Sparkles,
      title: "Prompt-Based Editing",
      description: "Just describe what you want. Our AI understands your intent."
    },
    {
      icon: Zap,
      title: "Lightning Fast",
      description: "No complex timelines. No learning curve. Just results."
    },
    {
      icon: DollarSign,
      title: "Cheap & Best",
      description: "Pay only for what you use. Starting at just ₹49."
    },
    {
      icon: Clock,
      title: "7-Day Downloads",
      description: "Your edited videos are available for 7 days. No rush."
    }
  ];

  return (
    <div className="min-h-screen pt-20" data-testid="landing-page">
      {/* Hero Section */}
      <section className="relative min-h-[80vh] flex flex-col items-center justify-center text-center px-6 overflow-hidden">
        {/* Background glow */}
        <div className="hero-glow" />
        
        {/* Content */}
        <div className="relative z-10 max-w-4xl mx-auto">
          {/* Tagline pill */}
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-primary/10 border border-primary/20 rounded-sm mb-8 animate-fade-in">
            <Scissors className="w-4 h-4 text-primary" />
            <span className="text-xs font-mono uppercase tracking-wider text-primary">
              Video Editing Simplified
            </span>
          </div>

          {/* Main headline */}
          <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight font-['Space_Grotesk'] mb-6 animate-fade-in-delay-1">
            Fed up editing on{" "}
            <span className="text-gradient">Complex Apps?</span>
          </h1>
          
          <p className="text-lg md:text-xl text-muted-foreground max-w-2xl mx-auto mb-4 animate-fade-in-delay-2">
            Canva, Adobe, DaVinci — too much to learn.{" "}
            <span className="text-foreground font-medium">We are here for you.</span>
          </p>

          <p className="text-2xl md:text-3xl font-bold text-foreground mb-8 animate-fade-in-delay-3 font-['Space_Grotesk']">
            You say. <span className="text-primary">We do the work.</span>
          </p>

          {/* CTA Buttons */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 animate-fade-in-delay-3">
            <Button 
              size="lg"
              className="bg-primary text-primary-foreground hover:bg-primary/90 font-bold uppercase tracking-wider px-8 py-6 rounded-sm text-base glow"
              onClick={handleGetStarted}
              data-testid="hero-get-started-btn"
            >
              {user ? "Open Editor" : "Get Started Free"}
              <ArrowRight className="w-5 h-5 ml-2" />
            </Button>
            <Button 
              variant="outline" 
              size="lg"
              className="border-white/20 hover:bg-white/5 px-8 py-6 rounded-sm"
              onClick={() => navigate("/help")}
              data-testid="hero-see-examples-btn"
            >
              <Play className="w-5 h-5 mr-2" />
              See Examples
            </Button>
          </div>

          {/* Trust indicators */}
          <div className="mt-12 flex items-center justify-center gap-8 text-muted-foreground text-sm">
            <span className="flex items-center gap-2">
              <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
              No credit card required
            </span>
            <span className="hidden sm:block">•</span>
            <span className="hidden sm:block">Pay per video from ₹49</span>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-24 px-6" data-testid="features-section">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-base md:text-lg text-primary font-mono uppercase tracking-wider mb-4">
              Why Choose Us
            </h2>
            <p className="text-3xl md:text-4xl font-bold font-['Space_Grotesk'] tracking-tight">
              Prompt your way through video editing
            </p>
          </div>

          {/* Bento Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {features.map((feature, index) => {
              const Icon = feature.icon;
              return (
                <div 
                  key={index}
                  className="glass-card rounded-sm p-6 group hover:border-primary/30 transition-all duration-300"
                  data-testid={`feature-card-${index}`}
                >
                  <div className="w-12 h-12 bg-primary/10 rounded-sm flex items-center justify-center mb-4 group-hover:bg-primary/20 transition-colors">
                    <Icon className="w-6 h-6 text-primary" />
                  </div>
                  <h3 className="text-lg font-bold font-['Space_Grotesk'] mb-2">
                    {feature.title}
                  </h3>
                  <p className="text-sm text-muted-foreground">
                    {feature.description}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="py-24 px-6 bg-secondary/30" data-testid="how-it-works-section">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-base md:text-lg text-primary font-mono uppercase tracking-wider mb-4">
              How It Works
            </h2>
            <p className="text-3xl md:text-4xl font-bold font-['Space_Grotesk'] tracking-tight">
              Three simple steps
            </p>
          </div>

          <div className="space-y-8">
            {[
              { step: "01", title: "Upload your video", desc: "Support for MP4, MKV, AVI, MOV and more. Up to 2GB." },
              { step: "02", title: "Write your prompt", desc: 'Example: "Keep: 00:00-00:12, 00:25-00:40. Order: 2,1. Output: mp4."' },
              { step: "03", title: "Download & share", desc: "Get your edited video in minutes. Download link valid for 7 days." }
            ].map((item, index) => (
              <div 
                key={index}
                className="flex items-start gap-6 p-6 glass-card rounded-sm"
                data-testid={`step-${index}`}
              >
                <span className="text-4xl font-bold text-primary/30 font-mono">
                  {item.step}
                </span>
                <div>
                  <h3 className="text-xl font-bold font-['Space_Grotesk'] mb-2">
                    {item.title}
                  </h3>
                  <p className="text-muted-foreground">
                    {item.desc}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="py-24 px-6" data-testid="final-cta-section">
        <div className="max-w-2xl mx-auto text-center">
          <h2 className="text-3xl md:text-4xl font-bold font-['Space_Grotesk'] tracking-tight mb-6">
            Ready to simplify your edits?
          </h2>
          <p className="text-muted-foreground mb-8">
            Join thousands of creators who've ditched complex software.
          </p>
          <Button 
            size="lg"
            className="bg-primary text-primary-foreground hover:bg-primary/90 font-bold uppercase tracking-wider px-12 py-6 rounded-sm text-base glow"
            onClick={handleGetStarted}
            data-testid="final-cta-btn"
          >
            Start Editing Now
            <ArrowRight className="w-5 h-5 ml-2" />
          </Button>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 px-6 border-t border-border">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Scissors className="w-5 h-5 text-primary" />
            <span className="font-bold font-['Space_Grotesk']">EDITCUE</span>
          </div>
          <p className="text-sm text-muted-foreground">
            © 2025 EditCue. All rights reserved.
          </p>
        </div>
      </footer>

      {/* Auth Modal */}
      <Dialog open={showAuthModal} onOpenChange={setShowAuthModal}>
        <DialogContent className="glass border-white/10 max-w-md" data-testid="auth-modal">
          <DialogHeader>
            <DialogTitle className="text-2xl font-bold font-['Space_Grotesk'] text-center">
              {otpSent ? "Enter OTP" : "Get Started"}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-6 pt-4">
            {!otpSent ? (
              <>
                {/* Google Login */}
                <Button 
                  className="w-full bg-white text-black hover:bg-gray-100 font-medium py-6"
                  onClick={handleGoogleLogin}
                  data-testid="google-login-btn"
                >
                  <svg className="w-5 h-5 mr-3" viewBox="0 0 24 24">
                    <path fill="currentColor" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                    <path fill="currentColor" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                    <path fill="currentColor" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                    <path fill="currentColor" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                  </svg>
                  Continue with Google
                </Button>

                <div className="relative">
                  <div className="absolute inset-0 flex items-center">
                    <span className="w-full border-t border-border" />
                  </div>
                  <div className="relative flex justify-center text-xs uppercase">
                    <span className="bg-background px-2 text-muted-foreground">Or</span>
                  </div>
                </div>

                {/* Email OTP */}
                <div className="space-y-4">
                  <Input 
                    type="email"
                    placeholder="Enter your email"
                    value={email}
                    onChange={(e) => {
                      const v = e.target.value;
                      setEmail(v);
                      if (!v) setEmailError("");
                      else if (!isValidEmail(v)) setEmailError("Invalid email format");
                      else setEmailError("");
                    }}
                    className="bg-input border-transparent focus:border-primary h-12"
                    data-testid="email-input"
                  />
                  {emailError && (
                    <div className="text-sm text-red-500 mt-2">{emailError}</div>
                  )}

                  <Button 
                    className="w-full bg-primary text-primary-foreground hover:bg-primary/90 py-6"
                    onClick={handleRequestOTP}
                    disabled={loading}
                    data-testid="request-otp-btn"
                  >
                    <Mail className="w-5 h-5 mr-2" />
                    {loading ? "Sending..." : "Continue with Email"}
                  </Button>
                </div>
              </>
            ) : (
              <div className="space-y-6">
                <p className="text-center text-muted-foreground">
                  We sent a code to <span className="text-foreground">{email}</span>
                </p>
                
                <div className="flex justify-center">
                  <InputOTP 
                    maxLength={6} 
                    value={otp} 
                    onChange={setOtp}
                    data-testid="otp-input"
                  >
                    <InputOTPGroup>
                      <InputOTPSlot index={0} />
                      <InputOTPSlot index={1} />
                      <InputOTPSlot index={2} />
                      <InputOTPSlot index={3} />
                      <InputOTPSlot index={4} />
                      <InputOTPSlot index={5} />
                    </InputOTPGroup>
                  </InputOTP>
                </div>

                <Button 
                  className="w-full bg-primary text-primary-foreground hover:bg-primary/90 py-6"
                  onClick={handleVerifyOTP}
                  disabled={loading || otp.length !== 6}
                  data-testid="verify-otp-btn"
                >
                  {loading ? "Verifying..." : "Verify & Continue"}
                </Button>

                <button 
                  className="w-full text-sm text-muted-foreground hover:text-foreground"
                  onClick={() => { setOtpSent(false); setOtp(""); }}
                  data-testid="back-to-email-btn"
                >
                  Use different email
                </button>
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Landing;
