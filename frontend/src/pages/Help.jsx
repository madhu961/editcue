import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { 
  Accordion, 
  AccordionContent, 
  AccordionItem, 
  AccordionTrigger 
} from "@/components/ui/accordion";
import { 
  ArrowLeft, 
  Copy, 
  Check, 
  Scissors, 
  Clock, 
  Shuffle, 
  FileVideo,
  Sparkles
} from "lucide-react";
import { toast } from "sonner";

const Help = () => {
  const navigate = useNavigate();
  const [copiedIndex, setCopiedIndex] = useState(null);

  const handleCopy = (text, index) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(index);
    toast.success("Prompt copied!");
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  const faqs = [
    {
      question: "How do I cut specific parts of my video?",
      answer: "Use the 'Keep' keyword followed by timecodes. Multiple segments are separated by commas.",
      example: "Keep: 00:00-00:30, 01:00-01:45, 02:30-03:00. Output: mp4.",
      icon: Scissors
    },
    {
      question: "Can I reorder the segments?",
      answer: "Yes! Use the 'Order' keyword with segment numbers. Segments are numbered in the order you list them.",
      example: "Keep: 00:00-00:15, 00:30-00:45, 01:00-01:15. Order: 3,1,2. Output: mp4.",
      icon: Shuffle
    },
    {
      question: "What time formats are supported?",
      answer: "Use mm:ss for minutes:seconds or hh:mm:ss for longer videos.",
      example: "Keep: 00:30-01:15, 02:00-02:45. Output: mp4. Quality: high.",
      icon: Clock
    },
    {
      question: "How do I extract just one segment?",
      answer: "Simply specify a single time range.",
      example: "Keep: 05:30-07:00. Output: mp4. Quality: medium.",
      icon: FileVideo
    },
    {
      question: "What quality options are available?",
      answer: "Choose from 'low', 'medium', or 'high'. Higher quality means larger file size.",
      example: "Keep: 00:00-02:00. Output: mp4. Quality: high.",
      icon: Sparkles
    },
    {
      question: "Can I change the output format?",
      answer: "Yes! Specify the output format. Supported: mp4 (recommended), webm, mkv.",
      example: "Keep: 00:00-01:00, 02:00-03:00. Order: 2,1. Output: webm. Quality: medium.",
      icon: FileVideo
    }
  ];

  const promptSyntax = [
    { keyword: "Keep:", description: "Time ranges to extract (required)", example: "Keep: 00:00-00:30, 01:00-01:30" },
    { keyword: "Order:", description: "Reorder segments (optional)", example: "Order: 2,1,3" },
    { keyword: "Output:", description: "Output format (optional, default: mp4)", example: "Output: mp4" },
    { keyword: "Quality:", description: "Quality preset (optional, default: medium)", example: "Quality: high" }
  ];

  return (
    <div className="min-h-screen pt-24 pb-12 px-6" data-testid="help-page">
      <div className="max-w-3xl mx-auto">
        {/* Header */}
        <div className="mb-12">
          <Button 
            variant="ghost" 
            onClick={() => navigate(-1)}
            className="mb-6"
            data-testid="back-btn"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back
          </Button>
          
          <h1 className="text-4xl font-bold font-['Space_Grotesk'] tracking-tight mb-4">
            Help & Examples
          </h1>
          <p className="text-lg text-muted-foreground">
            Learn how to write prompts to edit your videos exactly how you want.
          </p>
        </div>

        {/* Prompt Syntax Reference */}
        <section className="mb-12" data-testid="syntax-section">
          <h2 className="text-xl font-bold font-['Space_Grotesk'] mb-6 flex items-center gap-2">
            <span className="w-8 h-8 bg-primary/20 rounded-sm flex items-center justify-center">
              <Scissors className="w-4 h-4 text-primary" />
            </span>
            Prompt Syntax
          </h2>
          
          <div className="glass-card rounded-sm overflow-hidden">
            <table className="w-full" data-testid="syntax-table">
              <thead className="bg-secondary/50">
                <tr>
                  <th className="text-left p-4 font-mono text-sm text-primary">Keyword</th>
                  <th className="text-left p-4 text-sm text-muted-foreground">Description</th>
                  <th className="text-left p-4 text-sm text-muted-foreground hidden md:table-cell">Example</th>
                </tr>
              </thead>
              <tbody>
                {promptSyntax.map((item, index) => (
                  <tr key={index} className="border-t border-border">
                    <td className="p-4 font-mono text-sm font-bold">{item.keyword}</td>
                    <td className="p-4 text-sm text-muted-foreground">{item.description}</td>
                    <td className="p-4 font-mono text-xs text-foreground/80 hidden md:table-cell">{item.example}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        {/* FAQ Accordion */}
        <section data-testid="faq-section">
          <h2 className="text-xl font-bold font-['Space_Grotesk'] mb-6 flex items-center gap-2">
            <span className="w-8 h-8 bg-primary/20 rounded-sm flex items-center justify-center">
              <Sparkles className="w-4 h-4 text-primary" />
            </span>
            Common Scenarios
          </h2>

          <Accordion type="single" collapsible className="space-y-4">
            {faqs.map((faq, index) => {
              const Icon = faq.icon;
              return (
                <AccordionItem 
                  key={index} 
                  value={`item-${index}`}
                  className="glass-card rounded-sm border-white/10 px-6"
                  data-testid={`faq-item-${index}`}
                >
                  <AccordionTrigger className="hover:no-underline py-6">
                    <div className="flex items-center gap-4 text-left">
                      <Icon className="w-5 h-5 text-primary flex-shrink-0" />
                      <span className="font-medium">{faq.question}</span>
                    </div>
                  </AccordionTrigger>
                  <AccordionContent className="pb-6">
                    <div className="pl-9 space-y-4">
                      <p className="text-muted-foreground">{faq.answer}</p>
                      
                      {/* Example prompt */}
                      <div className="bg-secondary/50 rounded-sm p-4 border border-border">
                        <div className="flex items-center justify-between mb-2">
                          <span className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
                            Example Prompt
                          </span>
                          <Button 
                            variant="ghost" 
                            size="sm"
                            onClick={() => handleCopy(faq.example, index)}
                            data-testid={`copy-btn-${index}`}
                          >
                            {copiedIndex === index ? (
                              <Check className="w-4 h-4 text-green-500" />
                            ) : (
                              <Copy className="w-4 h-4" />
                            )}
                          </Button>
                        </div>
                        <code className="text-sm font-mono text-primary block break-all">
                          {faq.example}
                        </code>
                      </div>
                    </div>
                  </AccordionContent>
                </AccordionItem>
              );
            })}
          </Accordion>
        </section>

        {/* Quick Tips */}
        <section className="mt-12 p-6 glass-card rounded-sm" data-testid="tips-section">
          <h3 className="font-bold font-['Space_Grotesk'] mb-4">Quick Tips</h3>
          <ul className="space-y-2 text-sm text-muted-foreground">
            <li className="flex items-start gap-2">
              <span className="text-primary">•</span>
              Always ensure your start time is before your end time
            </li>
            <li className="flex items-start gap-2">
              <span className="text-primary">•</span>
              Use mm:ss format for videos under an hour
            </li>
            <li className="flex items-start gap-2">
              <span className="text-primary">•</span>
              Segment numbers in Order correspond to the order you listed them in Keep
            </li>
            <li className="flex items-start gap-2">
              <span className="text-primary">•</span>
              Higher quality = larger file size = longer processing time
            </li>
            <li className="flex items-start gap-2">
              <span className="text-primary">•</span>
              Download links expire after 7 days
            </li>
          </ul>
        </section>

        {/* CTA */}
        <div className="mt-12 text-center">
          <Button 
            className="bg-primary text-primary-foreground hover:bg-primary/90 font-bold uppercase tracking-wider px-8 py-6"
            onClick={() => navigate("/tool")}
            data-testid="start-editing-btn"
          >
            Start Editing
          </Button>
        </div>
      </div>
    </div>
  );
};

export default Help;
