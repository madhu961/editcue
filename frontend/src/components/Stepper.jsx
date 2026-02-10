import { Check } from "lucide-react";

const steps = [
  { id: 1, name: "Upload", description: "Select your video" },
  { id: 2, name: "Payment", description: "If required" },
  { id: 3, name: "Prompt", description: "Describe your edits" }
];

const Stepper = ({ currentStep, paymentRequired = false }) => {
  // Skip payment step if not required
  const visibleSteps = paymentRequired 
    ? steps 
    : steps.filter(s => s.id !== 2);
  
  const adjustedCurrentStep = !paymentRequired && currentStep > 1 
    ? currentStep - 1 
    : currentStep;

  return (
    <div className="w-full max-w-3xl mx-auto mb-12" data-testid="stepper">
      <div className="flex items-center justify-between">
        {visibleSteps.map((step, index) => {
          const stepNumber = paymentRequired ? step.id : (index + 1);
          const isActive = adjustedCurrentStep === stepNumber;
          const isCompleted = adjustedCurrentStep > stepNumber;
          
          return (
            <div key={step.id} className="flex items-center flex-1">
              {/* Step indicator */}
              <div className="flex flex-col items-center">
                <div 
                  className={`
                    w-10 h-10 rounded-sm flex items-center justify-center font-mono text-sm font-bold
                    transition-all duration-300
                    ${isCompleted 
                      ? "bg-primary text-primary-foreground" 
                      : isActive 
                        ? "bg-primary/20 text-primary border border-primary" 
                        : "bg-secondary text-muted-foreground border border-border"
                    }
                  `}
                  data-testid={`stepper-step-${step.id}`}
                >
                  {isCompleted ? <Check className="w-5 h-5" /> : stepNumber}
                </div>
                <span 
                  className={`
                    mt-2 text-xs font-mono uppercase tracking-wider
                    ${isActive ? "text-primary" : "text-muted-foreground"}
                  `}
                >
                  {step.name}
                </span>
              </div>
              
              {/* Connector line */}
              {index < visibleSteps.length - 1 && (
                <div className="flex-1 mx-4">
                  <div 
                    className={`
                      h-[2px] transition-all duration-500
                      ${isCompleted ? "bg-primary" : "bg-border"}
                    `}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default Stepper;
