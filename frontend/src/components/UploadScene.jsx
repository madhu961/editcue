// Simple CSS-based animation fallback (R3F has React 19 compatibility issues)
const UploadScene = ({ progress = 0 }) => {
  return (
    <div className="absolute inset-0 pointer-events-none overflow-hidden" data-testid="upload-3d-scene">
      {/* Animated background */}
      <div 
        className="absolute inset-0 flex items-center justify-center"
        style={{
          background: `radial-gradient(circle at center, rgba(204, 255, 0, ${0.05 + progress * 0.002}) 0%, transparent 70%)`
        }}
      >
        {/* Rotating wireframe cube (CSS) */}
        <div 
          className="relative"
          style={{
            width: `${150 + progress}px`,
            height: `${150 + progress}px`,
            animation: 'spin3d 8s linear infinite',
            transformStyle: 'preserve-3d',
          }}
        >
          {/* Cube faces */}
          {[...Array(6)].map((_, i) => (
            <div
              key={i}
              className="absolute inset-0 border-2 border-primary/40"
              style={{
                transform: [
                  'translateZ(75px)',
                  'rotateY(180deg) translateZ(75px)',
                  'rotateY(90deg) translateZ(75px)',
                  'rotateY(-90deg) translateZ(75px)',
                  'rotateX(90deg) translateZ(75px)',
                  'rotateX(-90deg) translateZ(75px)',
                ][i],
                background: `rgba(204, 255, 0, ${0.02 + progress * 0.0005})`,
              }}
            />
          ))}
        </div>
      </div>

      {/* Floating particles */}
      <div className="absolute inset-0">
        {[...Array(20)].map((_, i) => (
          <div
            key={i}
            className="absolute w-1 h-1 rounded-full bg-primary/60"
            style={{
              left: `${Math.random() * 100}%`,
              top: `${Math.random() * 100}%`,
              animation: `float ${3 + Math.random() * 4}s ease-in-out infinite`,
              animationDelay: `${Math.random() * 2}s`,
            }}
          />
        ))}
      </div>

      {/* Progress indicator ring */}
      <div className="absolute inset-0 flex items-center justify-center">
        <svg className="w-64 h-64 -rotate-90" viewBox="0 0 100 100">
          <circle
            cx="50"
            cy="50"
            r="45"
            stroke="currentColor"
            strokeWidth="0.5"
            fill="none"
            className="text-border"
          />
          <circle
            cx="50"
            cy="50"
            r="45"
            stroke="currentColor"
            strokeWidth="1"
            fill="none"
            strokeDasharray={`${progress * 2.83} 283`}
            strokeLinecap="round"
            className="text-primary transition-all duration-300"
          />
        </svg>
      </div>

      {/* CSS Animations */}
      <style>{`
        @keyframes spin3d {
          0% { transform: rotateX(0deg) rotateY(0deg); }
          100% { transform: rotateX(360deg) rotateY(360deg); }
        }
        @keyframes float {
          0%, 100% { transform: translateY(0) scale(1); opacity: 0.6; }
          50% { transform: translateY(-20px) scale(1.2); opacity: 1; }
        }
      `}</style>
    </div>
  );
};

export default UploadScene;
