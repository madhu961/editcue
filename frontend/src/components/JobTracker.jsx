import { useState, useEffect } from "react";
import axios from "axios";
import { API } from "@/App";
import { Button } from "@/components/ui/button";
import { Download, RefreshCw, Clock, CheckCircle, XCircle, Loader2, AlertTriangle } from "lucide-react";
import { toast } from "sonner";

const statusConfig = {
  queued: { 
    icon: Clock, 
    label: "Queued", 
    className: "status-queued" 
  },
  processing: { 
    icon: Loader2, 
    label: "Processing", 
    className: "status-processing",
    animate: true 
  },
  done: { 
    icon: CheckCircle, 
    label: "Done", 
    className: "status-done" 
  },
  failed: { 
    icon: XCircle, 
    label: "Failed", 
    className: "status-failed" 
  },
  expired: { 
    icon: AlertTriangle, 
    label: "Expired", 
    className: "status-expired" 
  }
};

const JobTracker = () => {
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchJobs = async () => {
    try {
      const response = await axios.get(`${API}/jobs`, { withCredentials: true });
      setJobs(response.data);
    } catch (error) {
      console.error("Failed to fetch jobs:", error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const handleRefresh = () => {
    setRefreshing(true);
    fetchJobs();
  };

  const handleDownload = async (jobId) => {
    try {
      const response = await axios.get(`${API}/jobs/${jobId}/download`, { 
        withCredentials: true 
      });
      
      // Open download URL
      window.open(response.data.download_url, "_blank");
      toast.success("Download started!");
    } catch (error) {
      if (error.response?.status === 410) {
        toast.error("Download link has expired");
      } else {
        toast.error("Failed to get download link");
      }
    }
  };

  useEffect(() => {
    fetchJobs();
    
    // Poll for updates every 5 seconds
    const interval = setInterval(fetchJobs, 5000);
    return () => clearInterval(interval);
  }, []);

  const formatDate = (dateStr) => {
    const date = new Date(dateStr);
    return date.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit"
    });
  };

  if (loading) {
    return (
      <div className="glass-card rounded-sm p-6" data-testid="job-tracker-loading">
        <div className="animate-pulse space-y-4">
          <div className="h-6 bg-secondary rounded w-1/3" />
          <div className="h-16 bg-secondary rounded" />
        </div>
      </div>
    );
  }

  return (
    <div className="glass-card rounded-sm p-6" data-testid="job-tracker">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-bold tracking-tight font-['Space_Grotesk'] uppercase">
          Your Jobs
        </h3>
        <Button 
          variant="ghost" 
          size="sm" 
          onClick={handleRefresh}
          disabled={refreshing}
          data-testid="job-tracker-refresh"
        >
          <RefreshCw className={`w-4 h-4 mr-2 ${refreshing ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {jobs.length === 0 ? (
        <div className="text-center py-8 text-muted-foreground" data-testid="job-tracker-empty">
          <p className="font-mono text-sm">No jobs yet. Upload a video to get started!</p>
        </div>
      ) : (
        <div className="space-y-3">
          {jobs.map((job) => {
            const config = statusConfig[job.status] || statusConfig.queued;
            const Icon = config.icon;
            
            return (
              <div 
                key={job.job_id}
                className="flex items-center justify-between p-4 bg-secondary/50 rounded-sm border border-border/50"
                data-testid={`job-item-${job.job_id}`}
              >
                <div className="flex items-center gap-4 flex-1 min-w-0">
                  {/* Status badge */}
                  <div className={`flex items-center gap-2 px-3 py-1 rounded-sm text-xs font-mono ${config.className}`}>
                    <Icon className={`w-3 h-3 ${config.animate ? "animate-spin" : ""}`} />
                    {config.label}
                  </div>
                  
                  {/* Job info */}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-mono truncate text-foreground" title={job.prompt_text}>
                      {job.prompt_text.substring(0, 50)}...
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {formatDate(job.created_at)}
                    </p>
                  </div>
                </div>

                {/* Download button */}
                {job.status === "done" && (
                  <Button 
                    size="sm"
                    className="bg-primary text-primary-foreground hover:bg-primary/90"
                    onClick={() => handleDownload(job.job_id)}
                    data-testid={`job-download-${job.job_id}`}
                  >
                    <Download className="w-4 h-4 mr-2" />
                    Download
                  </Button>
                )}

                {job.status === "failed" && job.error_message && (
                  <span className="text-xs text-destructive max-w-[200px] truncate" title={job.error_message}>
                    {job.error_message}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default JobTracker;
