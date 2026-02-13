import { useState, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth, API } from "@/App";
import axios from "axios";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Progress } from "@/components/ui/progress";
import { 
  Upload, 
  HelpCircle, 
  Send, 
  FileVideo, 
  X, 
  CreditCard,
  Check,
  AlertTriangle
} from "lucide-react";

import Stepper from "@/components/Stepper";
import JobTracker from "@/components/JobTracker";
import MetricsDisplay from "@/components/MetricsDisplay";
import UploadScene from "@/components/UploadScene";

const SUPPORTED_EXTENSIONS = ['mp4', 'mkv', 'avi', 'mov', 'mpeg', 'ogv', 'webm'];
const MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024; // 2GB
const PAYMENT_THRESHOLD = 200 * 1024 * 1024; // 200MB

const Tool = () => {
  const { user } = useAuth();
  const navigate = useNavigate();
  const fileInputRef = useRef(null);

  // State
  const [currentStep, setCurrentStep] = useState(1);
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [uploadComplete, setUploadComplete] = useState(false);
  const [videoId, setVideoId] = useState(null);
  const [paymentRequired, setPaymentRequired] = useState(false);
  const [paymentComplete, setPaymentComplete] = useState(false);
  const [quote, setQuote] = useState(null);
  const [prompt, setPrompt] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " MB";
    return (bytes / (1024 * 1024 * 1024)).toFixed(2) + " GB";
  };

  const validateFile = (file) => {
    const ext = file.name.split('.').pop().toLowerCase();
    
    if (!SUPPORTED_EXTENSIONS.includes(ext)) {
      toast.error(`Unsupported format. Supported: ${SUPPORTED_EXTENSIONS.join(', ')}`);
      return false;
    }
    
    if (file.size > MAX_FILE_SIZE) {
      toast.error("Unable to process files of this size at the moment.");
      return false;
    }
    
    return true;
  };

  const handleFileSelect = (e) => {
    const file = e.target.files?.[0];
    if (file && validateFile(file)) {
      setSelectedFile(file);
      setPaymentRequired(file.size > PAYMENT_THRESHOLD);
    }
  };

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (file && validateFile(file)) {
      setSelectedFile(file);
      setPaymentRequired(file.size > PAYMENT_THRESHOLD);
    }
  }, []);

  const handleDragOver = (e) => {
    e.preventDefault();
  };

  const handleUpload = async () => {
    if (!selectedFile) return;

    setUploading(true);
    setUploadProgress(0);

    try {
      // Initialize upload
      const ext = selectedFile.name.split('.').pop().toLowerCase();
      const initResponse = await axios.post(
        `${API}/uploads/init`,
        {
          filename: selectedFile.name,
          size_bytes: selectedFile.size,
          ext: ext
        },
        { withCredentials: true }
      );

      const { presigned_url, object_key, requires_payment, quote: initQuote } = initResponse.data;
      setPaymentRequired(requires_payment);
      if (initQuote) setQuote(initQuote);

    // Upload file to Spaces using XHR (forces Origin header + supports progress)
    await new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("PUT", presigned_url, true);

    // Must match what Spaces expects; safe default is octet-stream
    xhr.setRequestHeader("Content-Type", selectedFile.type || "application/octet-stream");

    xhr.upload.onprogress = (evt) => {
      if (!evt.lengthComputable) return;
      const progress = Math.round((evt.loaded / evt.total) * 100);
      setUploadProgress(progress);
  };

  xhr.onload = () => {
    if (xhr.status >= 200 && xhr.status < 300) resolve();
    else reject(new Error(`Spaces PUT failed: ${xhr.status} ${xhr.responseText || ""}`));
  };

  xhr.onerror = () => reject(new Error("Spaces PUT network error"));
  xhr.send(selectedFile);
});


      // Complete upload
      const completeResponse = await axios.post(
        `${API}/uploads/complete`,
        {
          object_key: object_key,
          size_bytes: selectedFile.size
        },
        { withCredentials: true }
      );

      setVideoId(completeResponse.data.video_id);
      setUploadComplete(true);
      
      // Move to next step
      if (requires_payment) {
        setCurrentStep(2);
      } else {
        setPaymentComplete(true);
        setCurrentStep(3);
      }

      toast.success("Upload complete!");
    } catch (error) {
      console.error("Upload error:", error);
      toast.error(error.response?.data?.detail || "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const handleMockPayment = async () => {
    if (!videoId) return;

    try {
      await axios.post(
        `${API}/billing/mock-complete?video_id=${videoId}`,
        {},
        { withCredentials: true }
      );
      
      setPaymentComplete(true);
      setCurrentStep(3);
      toast.success("Payment successful! (MOCKED)");
    } catch (error) {
      toast.error("Payment failed");
    }
  };

  const handleSubmitJob = async () => {
    if (!videoId || !prompt.trim()) {
      toast.error("Please enter a prompt");
      return;
    }

    if (prompt.length > 1000) {
      toast.error("Prompt exceeds 1000 characters");
      return;
    }

    setSubmitting(true);
    try {
      const response = await axios.post(
        `${API}/jobs`,
        {
          video_id: videoId,
          prompt_text: prompt
        },
        { withCredentials: true }
      );

      toast.success("Job submitted! Check the tracker below.");
      
      // Reset form for new upload
      setSelectedFile(null);
      setUploadProgress(0);
      setUploadComplete(false);
      setVideoId(null);
      setPaymentRequired(false);
      setPaymentComplete(false);
      setQuote(null);
      setPrompt("");
      setCurrentStep(1);
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to submit job");
    } finally {
      setSubmitting(false);
    }
  };

  const handleReset = () => {
    setSelectedFile(null);
    setUploadProgress(0);
    setUploadComplete(false);
    setVideoId(null);
    setPaymentRequired(false);
    setPaymentComplete(false);
    setQuote(null);
    setPrompt("");
    setCurrentStep(1);
  };

  const samplePrompt = "Keep: 00:00-00:12, 00:25-00:40, 01:10-01:30. Order: 2,1,3. Output: mp4. Quality: medium.";

  return (
    <div className="min-h-screen pt-24 pb-12 px-6" data-testid="tool-page">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold font-['Space_Grotesk'] tracking-tight mb-2">
            Video Editor
          </h1>
          <p className="text-muted-foreground">
            Upload, prompt, download. It's that simple.
          </p>
        </div>

        {/* Stepper */}
        <Stepper currentStep={currentStep} paymentRequired={paymentRequired} />

        {/* Main Content Area */}
        <div className="glass-card rounded-sm p-8 mb-8 relative overflow-hidden min-h-[400px]">
          {/* 3D Background during upload */}
          {uploading && <UploadScene progress={uploadProgress} />}

          {/* Step 1: Upload */}
          {currentStep === 1 && (
            <div className="relative z-10" data-testid="upload-step">
              {!selectedFile ? (
                <div 
                  className="dropzone"
                  onDrop={handleDrop}
                  onDragOver={handleDragOver}
                  onClick={() => fileInputRef.current?.click()}
                  data-testid="dropzone"
                >
                  <input 
                    ref={fileInputRef}
                    type="file"
                    accept={SUPPORTED_EXTENSIONS.map(ext => `.${ext}`).join(',')}
                    onChange={handleFileSelect}
                    className="hidden"
                    data-testid="file-input"
                  />
                  <Upload className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
                  <p className="text-lg font-medium mb-2">
                    Drop your video here or click to browse
                  </p>
                  <p className="text-sm text-muted-foreground">
                    Supports: {SUPPORTED_EXTENSIONS.join(', ')} • Max 2GB
                  </p>
                </div>
              ) : (
                <div className="space-y-6">
                  {/* File info */}
                  <div className="flex items-center justify-between p-4 bg-secondary/50 rounded-sm border border-border">
                    <div className="flex items-center gap-4">
                      <FileVideo className="w-10 h-10 text-primary" />
                      <div>
                        <p className="font-medium truncate max-w-[300px]" data-testid="selected-file-name">
                          {selectedFile.name}
                        </p>
                        <p className="text-sm text-muted-foreground" data-testid="selected-file-size">
                          {formatFileSize(selectedFile.size)}
                          {paymentRequired && (
                            <span className="ml-2 text-yellow-400">
                              • Payment required
                            </span>
                          )}
                        </p>
                      </div>
                    </div>
                    <Button 
                      variant="ghost" 
                      size="icon"
                      onClick={handleReset}
                      disabled={uploading}
                      data-testid="remove-file-btn"
                    >
                      <X className="w-5 h-5" />
                    </Button>
                  </div>

                  {/* Upload progress */}
                  {uploading && (
                    <div className="space-y-2" data-testid="upload-progress">
                      <div className="flex justify-between text-sm">
                        <span className="text-muted-foreground">Uploading...</span>
                        <span className="font-mono text-primary">{uploadProgress}%</span>
                      </div>
                      <Progress value={uploadProgress} className="h-2" />
                    </div>
                  )}

                  {/* Upload button */}
                  {!uploading && !uploadComplete && (
                    <Button 
                      className="w-full bg-primary text-primary-foreground hover:bg-primary/90 py-6 font-bold uppercase tracking-wider"
                      onClick={handleUpload}
                      data-testid="upload-btn"
                    >
                      <Upload className="w-5 h-5 mr-2" />
                      Start Upload
                    </Button>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Step 2: Payment (if required) */}
          {currentStep === 2 && paymentRequired && !paymentComplete && (
            <div className="relative z-10 text-center" data-testid="payment-step">
              <CreditCard className="w-16 h-16 text-primary mx-auto mb-6" />
              <h2 className="text-2xl font-bold font-['Space_Grotesk'] mb-4">
                Payment Required
              </h2>
              <p className="text-muted-foreground mb-6">
                Your video is larger than 200MB. A small fee is required to process it.
              </p>
              
              {quote && (
                <div className="inline-block p-6 bg-secondary/50 rounded-sm border border-border mb-6">
                  <p className="text-sm text-muted-foreground mb-2">One-time payment</p>
                  <p className="text-4xl font-bold text-primary font-['Space_Grotesk']">
                    ₹{quote.amount}
                  </p>
                </div>
              )}

              <div className="flex flex-col gap-4 max-w-xs mx-auto">
                <Button 
                  className="bg-primary text-primary-foreground hover:bg-primary/90 py-6 font-bold uppercase tracking-wider"
                  onClick={handleMockPayment}
                  data-testid="pay-btn"
                >
                  Pay Now (MOCKED)
                </Button>
                <p className="text-xs text-muted-foreground">
                  <AlertTriangle className="w-3 h-3 inline mr-1" />
                  Razorpay integration is mocked for demo
                </p>
              </div>
            </div>
          )}

          {/* Step 3: Prompt */}
          {currentStep === 3 && (
            <div className="relative z-10" data-testid="prompt-step">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-bold font-['Space_Grotesk']">
                  Describe Your Edits
                </h2>
                <Button 
                  variant="ghost" 
                  size="icon"
                  onClick={() => navigate("/help")}
                  data-testid="prompt-help-btn"
                >
                  <HelpCircle className="w-5 h-5 text-muted-foreground" />
                </Button>
              </div>

              <div className="space-y-4">
                <Textarea 
                  placeholder={samplePrompt}
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  className="min-h-[150px] bg-input border-transparent focus:border-primary font-mono text-sm resize-none"
                  maxLength={1000}
                  data-testid="prompt-textarea"
                />
                
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">
                    {prompt.length}/1000 characters
                  </span>
                  <button 
                    className="text-primary hover:underline text-sm"
                    onClick={() => setPrompt(samplePrompt)}
                    data-testid="use-sample-prompt-btn"
                  >
                    Use sample prompt
                  </button>
                </div>

                <Button 
                  className="w-full bg-primary text-primary-foreground hover:bg-primary/90 py-6 font-bold uppercase tracking-wider"
                  onClick={handleSubmitJob}
                  disabled={!prompt.trim() || submitting}
                  data-testid="submit-job-btn"
                >
                  {submitting ? (
                    "Submitting..."
                  ) : (
                    <>
                      <Send className="w-5 h-5 mr-2" />
                      Submit Job
                    </>
                  )}
                </Button>
              </div>
            </div>
          )}

          {/* Success state indicator */}
          {uploadComplete && currentStep === 1 && (
            <div className="absolute inset-0 bg-background/80 flex items-center justify-center">
              <div className="text-center">
                <Check className="w-16 h-16 text-green-500 mx-auto mb-4" />
                <p className="text-lg font-medium">Upload Complete!</p>
              </div>
            </div>
          )}
        </div>

        {/* Job Tracker */}
        <div className="mb-8">
          <JobTracker />
        </div>

        {/* Metrics */}
        <MetricsDisplay />
      </div>
    </div>
  );
};

export default Tool;
