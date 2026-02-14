import { Check } from "lucide-react";

/**
 * Pay-first Stepper
 *
 * Visible steps:
 * - If paymentRequired:   1 Reserve -> 2 Pay -> 3 Upload -> 4 Prompt
 * - If not required:      1 Reserve -> 2 Upload -> 3 Prompt
 *
 * Active step logic:
 * - If payment required:
 *    - currentStep === 1 => Reserve
 *    - else if !paymentComplete => Pay
 *    - else if paymentComplete && !uploadComplete => Upload (2.5)
 *    - else => Prompt
 * - If not required:
 *    - currentStep === 1 && !uploadComplete => Reserve
 *    - !uploadComplete => Upload
 *    - else => Prompt
 */
const Stepper = ({
  currentStep = 1,
  paymentRequired = false,
  paymentComplete = false,
  uploadComplete = false
}) => {
  const stepsPaid = [
    { id: 1, name: "Reserve & Quote", description: "Create upload session" },
    { id: 2, name: "Pay", description: "Razorpay payment" },
    { id: 3, name: "Upload", description: "Send to storage" },
    { id: 4, name: "Prompt", description: "Describe your edits" }
  ];

  const stepsFree = [
    { id: 1, name: "Reserve & Quote", description: "Create upload session" },
    { id: 2, name: "Upload", description: "Send to storage" },
    { id: 3, name: "Prompt", description: "Describe your edits" }
  ];

  const visibleSteps = paymentRequired ? stepsPaid : stepsFree;

  const getActiveStepId = () => {
    if (paymentRequired) {
      if (currentStep === 1) return 1;
      if (!paymentComplete) return 2;
      if (paymentComplete && !uploadComplete) return 3; // "2.5"
      return 4;
    }

    // No payment required
    if (currentStep === 1 && !uploadComplete) return 1;
    if (!uploadComplete) return 2;
    return 3;
  };

  const activeStepId = getActiveStepId();

  return (
    <div className="w-full max-w-3xl mx-auto mb-12" data-testid="stepper">
      <div className="flex items-center justify-between">
        {visibleSteps.map((step, index) => {
          const isActive = activeStepId === step.id;
          const isCompleted = activeStepId > step.id;

          return (
            <div key={step.id} className="flex items-center flex-1">
              {/* Step indicator */}
              <div className="flex flex-col items-center">
                <div
                  className={`
                    w-10 h-10 rounded-sm flex items-center justify-center font-mono text-sm font-bold
                    transition-all duration-300
                    ${
                      isCompleted
                        ? "bg-primary text-primary-foreground"
                        : isActive
                        ? "bg-primary/20 text-primary border border-primary"
                        : "bg-secondary text-muted-foreground border border-border"
                    }
                  `}
                  data-testid={`stepper-step-${step.id}`}
                >
                  {isCompleted ? <Check className="w-5 h-5" /> : step.id}
                </div>

                <span
                  className={`
                    mt-2 text-xs font-mono uppercase tracking-wider text-center
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

