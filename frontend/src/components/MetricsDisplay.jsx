import { useState, useEffect } from "react";
import axios from "axios";
import { API } from "@/App";
import { Users, Video, TrendingUp, Calendar } from "lucide-react";

const MetricsDisplay = () => {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        const response = await axios.get(`${API}/metrics/summary`);
        setMetrics(response.data);
      } catch (error) {
        console.error("Failed to fetch metrics:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchMetrics();
  }, []);

  if (loading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4" data-testid="metrics-loading">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="glass-card rounded-sm p-4 animate-pulse">
            <div className="h-4 bg-secondary rounded w-2/3 mb-2" />
            <div className="h-8 bg-secondary rounded w-1/2" />
          </div>
        ))}
      </div>
    );
  }

  if (!metrics) return null;

  const items = [
    {
      label: "Lifetime Visitors",
      value: metrics.lifetime_visitors.toLocaleString(),
      icon: Users,
      color: "text-blue-400"
    },
    {
      label: "Videos Processed",
      value: metrics.lifetime_videos_processed.toLocaleString(),
      icon: Video,
      color: "text-primary"
    },
    {
      label: "Today's Visitors",
      value: metrics.today_visitors.toLocaleString(),
      icon: Calendar,
      color: "text-purple-400"
    },
    {
      label: "Processed Today",
      value: metrics.today_videos_processed.toLocaleString(),
      icon: TrendingUp,
      color: "text-green-400"
    }
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4" data-testid="metrics-display">
      {items.map((item, index) => {
        const Icon = item.icon;
        return (
          <div 
            key={index}
            className="glass-card rounded-sm p-4 group hover:border-primary/30 transition-colors"
            data-testid={`metric-${index}`}
          >
            <div className="flex items-center gap-2 mb-2">
              <Icon className={`w-4 h-4 ${item.color}`} />
              <span className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
                {item.label}
              </span>
            </div>
            <p className="text-2xl font-bold font-['Space_Grotesk'] text-foreground">
              {item.value}
            </p>
          </div>
        );
      })}
    </div>
  );
};

export default MetricsDisplay;
