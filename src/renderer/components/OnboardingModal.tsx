import React, { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  ChevronRight,
  ChevronLeft,
  SkipForward,
  Sparkles,
  Target,
  KeyRound,
  Palette,
  Rocket,
  Check,
  Sun,
  Moon,
  Monitor,
  ChevronDown,
  ChevronUp,
  Eye,
  EyeOff,
} from "lucide-react";
import useAppStore from "../stores/useAppStore";

const stepVariants = {
  enter: (direction: number) => ({
    x: direction > 0 ? 60 : -60,
    opacity: 0,
  }),
  center: {
    x: 0,
    opacity: 1,
  },
  exit: (direction: number) => ({
    x: direction < 0 ? 60 : -60,
    opacity: 0,
  }),
};

const OnboardingModal: React.FC = () => {
  const [step, setStep] = useState(0);
  const [direction, setDirection] = useState(1);
  const [goal, setGoal] = useState("");
  const [theme, setThemeState] = useState<"dark" | "light" | "system">("dark");
  const [openAiKey, setOpenAiKey] = useState("");
  const [anthropicKey, setAnthropicKey] = useState("");
  const [googleKey, setGoogleKey] = useState("");
  const [showKeys, setShowKeys] = useState({
    openai: false,
    anthropic: false,
    google: false,
  });
  const [expandedSection, setExpandedSection] = useState<string | null>(null);

  const setOnboardingComplete = useAppStore((s) => s.setOnboardingComplete);
  const setTheme = useAppStore((s) => s.setTheme);

  const totalSteps = 5;

  const goNext = useCallback(() => {
    if (step < totalSteps - 1) {
      setDirection(1);
      setStep((s) => s + 1);
    }
  }, [step, totalSteps]);

  const goBack = useCallback(() => {
    if (step > 0) {
      setDirection(-1);
      setStep((s) => s - 1);
    }
  }, [step]);

  const handleComplete = useCallback(() => {
    setTheme(theme);
    setOnboardingComplete(true);
    // Persist to localStorage as fallback
    try {
      localStorage.setItem("construct_onboarding_complete", "true");
      localStorage.setItem("construct_theme", theme);
    } catch {
      // Ignore storage errors
    }
  }, [theme, setTheme, setOnboardingComplete]);

  const handleSkip = useCallback(() => {
    setOnboardingComplete(true);
    try {
      localStorage.setItem("construct_onboarding_complete", "true");
    } catch {
      // Ignore
    }
  }, [setOnboardingComplete]);

  const toggleSection = (section: string) => {
    setExpandedSection((prev) => (prev === section ? null : section));
  };

  const goalExamples = [
    "Build a React dashboard with real-time data",
    "Create a REST API with authentication",
    "Set up a CI/CD pipeline for my project",
    "Refactor legacy code to modern TypeScript",
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <motion.div
        initial={{ opacity: 0, scale: 0.95, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ type: "spring", stiffness: 300, damping: 25 }}
        className="glass-panel rounded-2xl w-full max-w-lg mx-4 overflow-hidden shadow-2xl"
      >
        {/* Skip button */}
        <button
          onClick={handleSkip}
          className="absolute top-4 right-4 flex items-center gap-1.5 text-xs text-construct-text-muted hover:text-construct-text-primary transition-colors z-10"
        >
          Skip
          <SkipForward className="w-3.5 h-3.5" />
        </button>

        {/* Content area */}
        <div className="relative min-h-[380px] overflow-hidden">
          <AnimatePresence mode="wait" custom={direction}>
            <motion.div
              key={step}
              custom={direction}
              variants={stepVariants}
              initial="enter"
              animate="center"
              exit="exit"
              transition={{ duration: 0.25, ease: "easeInOut" }}
              className="p-8"
            >
              {/* Step 1: Welcome */}
              {step === 0 && (
                <div className="flex flex-col items-center text-center space-y-6">
                  {/* Animated Logo */}
                  <div className="relative">
                    <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-construct-accent-primary/20 to-construct-accent-primary/5 border border-construct-accent-primary/30 flex items-center justify-center pulse-glow">
                      <span className="text-3xl font-bold text-construct-accent-primary">
                        C
                      </span>
                    </div>
                    <div className="absolute -bottom-1 -right-1 w-6 h-6 rounded-full bg-construct-accent-primary/20 border border-construct-accent-primary/30 flex items-center justify-center">
                      <Sparkles className="w-3.5 h-3.5 text-construct-accent-primary" />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <h1 className="text-2xl font-bold text-construct-text-primary">
                      Welcome to Construct
                    </h1>
                    <p className="text-sm text-construct-text-muted leading-relaxed max-w-xs mx-auto">
                      Your AI-powered development companion. Let&apos;s get you
                      set up in just a few steps.
                    </p>
                  </div>

                  <div className="flex gap-2">
                    {["Plan", "Code", "Ship"].map((item, i) => (
                      <motion.span
                        key={item}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: 0.2 + i * 0.1 }}
                        className="px-3 py-1 rounded-full text-xs font-medium bg-construct-accent-primary/10 text-construct-accent-primary border border-construct-accent-primary/20"
                      >
                        {item}
                      </motion.span>
                    ))}
                  </div>
                </div>
              )}

              {/* Step 2: Set Goal */}
              {step === 1 && (
                <div className="flex flex-col space-y-6">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-construct-accent-primary/10 flex items-center justify-center">
                      <Target className="w-5 h-5 text-construct-accent-primary" />
                    </div>
                    <div>
                      <h2 className="text-lg font-semibold text-construct-text-primary">
                        Set Your First Goal
                      </h2>
                      <p className="text-xs text-construct-text-muted">
                        What would you like to build or accomplish?
                      </p>
                    </div>
                  </div>

                  <textarea
                    value={goal}
                    onChange={(e) => setGoal(e.target.value)}
                    placeholder="Describe your project or goal..."
                    className="w-full h-24 px-4 py-3 rounded-xl bg-construct-bg-primary/60 border border-construct-border/50 text-sm text-construct-text-primary placeholder:text-construct-text-muted/50 focus:outline-none focus:border-construct-accent-primary/50 focus:ring-1 focus:ring-construct-accent-primary/20 resize-none transition-all"
                  />

                  <div className="space-y-2">
                    <p className="text-xs text-construct-text-muted font-medium">
                      Or pick an example:
                    </p>
                    <div className="grid grid-cols-1 gap-2">
                      {goalExamples.map((example) => (
                        <button
                          key={example}
                          onClick={() => setGoal(example)}
                          className={`text-left px-3 py-2.5 rounded-lg text-xs transition-all border ${
                            goal === example
                              ? "bg-construct-accent-primary/10 border-construct-accent-primary/30 text-construct-accent-primary"
                              : "bg-construct-bg-primary/40 border-construct-border/30 text-construct-text-muted hover:bg-construct-bg-primary/60 hover:text-construct-text-primary"
                          }`}
                        >
                          {example}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* Step 3: API Keys */}
              {step === 2 && (
                <div className="flex flex-col space-y-5">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-construct-accent-primary/10 flex items-center justify-center">
                      <KeyRound className="w-5 h-5 text-construct-accent-primary" />
                    </div>
                    <div>
                      <h2 className="text-lg font-semibold text-construct-text-primary">
                        Configure API Keys
                      </h2>
                      <p className="text-xs text-construct-text-muted">
                        Add your AI provider API keys (optional for now)
                      </p>
                    </div>
                  </div>

                  <div className="space-y-2">
                    {/* OpenAI */}
                    <div className="rounded-xl border border-construct-border/40 overflow-hidden">
                      <button
                        onClick={() => toggleSection("openai")}
                        className="w-full flex items-center justify-between px-4 py-3 text-sm text-construct-text-primary hover:bg-white/[0.02] transition-colors"
                      >
                        <span className="font-medium">OpenAI</span>
                        {expandedSection === "openai" ? (
                          <ChevronUp className="w-4 h-4 text-construct-text-muted" />
                        ) : (
                          <ChevronDown className="w-4 h-4 text-construct-text-muted" />
                        )}
                      </button>
                      <AnimatePresence>
                        {expandedSection === "openai" && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: "auto", opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{ duration: 0.2 }}
                            className="overflow-hidden"
                          >
                            <div className="px-4 pb-3 flex gap-2">
                              <div className="relative flex-1">
                                <input
                                  type={showKeys.openai ? "text" : "password"}
                                  value={openAiKey}
                                  onChange={(e) => setOpenAiKey(e.target.value)}
                                  placeholder="sk-..."
                                  className="w-full px-3 py-2 rounded-lg bg-construct-bg-primary/60 border border-construct-border/50 text-xs text-construct-text-primary placeholder:text-construct-text-muted/50 focus:outline-none focus:border-construct-accent-primary/50 pr-8"
                                />
                                <button
                                  onClick={() =>
                                    setShowKeys((p) => ({
                                      ...p,
                                      openai: !p.openai,
                                    }))
                                  }
                                  className="absolute right-2 top-1/2 -translate-y-1/2 text-construct-text-muted hover:text-construct-text-primary"
                                >
                                  {showKeys.openai ? (
                                    <EyeOff className="w-3.5 h-3.5" />
                                  ) : (
                                    <Eye className="w-3.5 h-3.5" />
                                  )}
                                </button>
                              </div>
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>

                    {/* Anthropic */}
                    <div className="rounded-xl border border-construct-border/40 overflow-hidden">
                      <button
                        onClick={() => toggleSection("anthropic")}
                        className="w-full flex items-center justify-between px-4 py-3 text-sm text-construct-text-primary hover:bg-white/[0.02] transition-colors"
                      >
                        <span className="font-medium">Anthropic</span>
                        {expandedSection === "anthropic" ? (
                          <ChevronUp className="w-4 h-4 text-construct-text-muted" />
                        ) : (
                          <ChevronDown className="w-4 h-4 text-construct-text-muted" />
                        )}
                      </button>
                      <AnimatePresence>
                        {expandedSection === "anthropic" && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: "auto", opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{ duration: 0.2 }}
                            className="overflow-hidden"
                          >
                            <div className="px-4 pb-3 flex gap-2">
                              <div className="relative flex-1">
                                <input
                                  type={
                                    showKeys.anthropic ? "text" : "password"
                                  }
                                  value={anthropicKey}
                                  onChange={(e) =>
                                    setAnthropicKey(e.target.value)
                                  }
                                  placeholder="sk-ant-..."
                                  className="w-full px-3 py-2 rounded-lg bg-construct-bg-primary/60 border border-construct-border/50 text-xs text-construct-text-primary placeholder:text-construct-text-muted/50 focus:outline-none focus:border-construct-accent-primary/50 pr-8"
                                />
                                <button
                                  onClick={() =>
                                    setShowKeys((p) => ({
                                      ...p,
                                      anthropic: !p.anthropic,
                                    }))
                                  }
                                  className="absolute right-2 top-1/2 -translate-y-1/2 text-construct-text-muted hover:text-construct-text-primary"
                                >
                                  {showKeys.anthropic ? (
                                    <EyeOff className="w-3.5 h-3.5" />
                                  ) : (
                                    <Eye className="w-3.5 h-3.5" />
                                  )}
                                </button>
                              </div>
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>

                    {/* Google */}
                    <div className="rounded-xl border border-construct-border/40 overflow-hidden">
                      <button
                        onClick={() => toggleSection("google")}
                        className="w-full flex items-center justify-between px-4 py-3 text-sm text-construct-text-primary hover:bg-white/[0.02] transition-colors"
                      >
                        <span className="font-medium">Google AI</span>
                        {expandedSection === "google" ? (
                          <ChevronUp className="w-4 h-4 text-construct-text-muted" />
                        ) : (
                          <ChevronDown className="w-4 h-4 text-construct-text-muted" />
                        )}
                      </button>
                      <AnimatePresence>
                        {expandedSection === "google" && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: "auto", opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{ duration: 0.2 }}
                            className="overflow-hidden"
                          >
                            <div className="px-4 pb-3 flex gap-2">
                              <div className="relative flex-1">
                                <input
                                  type={showKeys.google ? "text" : "password"}
                                  value={googleKey}
                                  onChange={(e) => setGoogleKey(e.target.value)}
                                  placeholder="AIza..."
                                  className="w-full px-3 py-2 rounded-lg bg-construct-bg-primary/60 border border-construct-border/50 text-xs text-construct-text-primary placeholder:text-construct-text-muted/50 focus:outline-none focus:border-construct-accent-primary/50 pr-8"
                                />
                                <button
                                  onClick={() =>
                                    setShowKeys((p) => ({
                                      ...p,
                                      google: !p.google,
                                    }))
                                  }
                                  className="absolute right-2 top-1/2 -translate-y-1/2 text-construct-text-muted hover:text-construct-text-primary"
                                >
                                  {showKeys.google ? (
                                    <EyeOff className="w-3.5 h-3.5" />
                                  ) : (
                                    <Eye className="w-3.5 h-3.5" />
                                  )}
                                </button>
                              </div>
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  </div>

                  <p className="text-[11px] text-construct-text-muted/70 text-center">
                    API keys are stored locally and never sent to our servers.
                    You can skip this step and configure later in settings.
                  </p>
                </div>
              )}

              {/* Step 4: Theme */}
              {step === 3 && (
                <div className="flex flex-col space-y-6">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-construct-accent-primary/10 flex items-center justify-center">
                      <Palette className="w-5 h-5 text-construct-accent-primary" />
                    </div>
                    <div>
                      <h2 className="text-lg font-semibold text-construct-text-primary">
                        Choose Your Theme
                      </h2>
                      <p className="text-xs text-construct-text-muted">
                        Select your preferred appearance
                      </p>
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-3">
                    {([
                      {
                        value: "dark" as const,
                        label: "Dark",
                        icon: Moon,
                        preview:
                          "bg-construct-bg-primary border-construct-border text-construct-text-primary",
                      },
                      {
                        value: "light" as const,
                        label: "Light",
                        icon: Sun,
                        preview:
                          "bg-[#f1f5f9] border-[#ccd0da] text-[#4c4f69]",
                      },
                      {
                        value: "system" as const,
                        label: "System",
                        icon: Monitor,
                        preview:
                          "bg-gradient-to-br from-construct-bg-primary to-[#f1f5f9] border-construct-border text-construct-text-primary",
                      },
                    ] as const).map((option) => {
                      const Icon = option.icon;
                      const isSelected = theme === option.value;
                      return (
                        <button
                          key={option.value}
                          onClick={() => setThemeState(option.value)}
                          className={`relative flex flex-col items-center gap-3 p-4 rounded-xl border-2 transition-all ${
                            isSelected
                              ? "border-construct-accent-primary bg-construct-accent-primary/5"
                              : "border-construct-border/30 bg-construct-bg-primary/30 hover:border-construct-border/60"
                          }`}
                        >
                          {/* Preview card */}
                          <div
                            className={`w-full h-16 rounded-lg border ${option.preview} flex flex-col gap-1.5 p-2`}
                          >
                            <div className="w-full h-1.5 rounded-full bg-current opacity-20" />
                            <div className="w-2/3 h-1.5 rounded-full bg-current opacity-20" />
                            <div className="w-full h-1.5 rounded-full bg-current opacity-20" />
                          </div>
                          <div className="flex items-center gap-1.5">
                            <Icon
                              className={`w-3.5 h-3.5 ${
                                isSelected
                                  ? "text-construct-accent-primary"
                                  : "text-construct-text-muted"
                              }`}
                            />
                            <span
                              className={`text-xs font-medium ${
                                isSelected
                                  ? "text-construct-accent-primary"
                                  : "text-construct-text-muted"
                              }`}
                            >
                              {option.label}
                            </span>
                          </div>
                          {isSelected && (
                            <div className="absolute top-2 right-2 w-5 h-5 rounded-full bg-construct-accent-primary flex items-center justify-center">
                              <Check className="w-3 h-3 text-white" />
                            </div>
                          )}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Step 5: Ready */}
              {step === 4 && (
                <div className="flex flex-col items-center text-center space-y-6">
                  <motion.div
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    transition={{
                      type: "spring",
                      stiffness: 300,
                      damping: 20,
                      delay: 0.1,
                    }}
                    className="w-20 h-20 rounded-2xl bg-gradient-to-br from-green-500/20 to-green-500/5 border border-green-500/30 flex items-center justify-center glow-success"
                  >
                    <Rocket className="w-9 h-9 text-green-400" />
                  </motion.div>

                  <div className="space-y-2">
                    <h2 className="text-2xl font-bold text-construct-text-primary">
                      Ready to Go!
                    </h2>
                    <p className="text-sm text-construct-text-muted leading-relaxed max-w-xs mx-auto">
                      Construct is all set up. Let&apos;s start building
                      something amazing together.
                    </p>
                  </div>

                  {/* Summary */}
                  <div className="w-full rounded-xl bg-construct-bg-primary/50 border border-construct-border/30 p-4 space-y-2.5 text-left">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-construct-text-muted">Goal</span>
                      <span className="text-construct-text-primary truncate max-w-[200px]">
                        {goal || "Not set"}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-construct-text-muted">Theme</span>
                      <span className="text-construct-text-primary capitalize">
                        {theme}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-construct-text-muted">
                        API Keys
                      </span>
                      <span className="text-construct-text-primary">
                        {[
                          openAiKey && "OpenAI",
                          anthropicKey && "Anthropic",
                          googleKey && "Google",
                        ]
                          .filter(Boolean)
                          .join(", ") || "None configured"}
                      </span>
                    </div>
                  </div>

                  <motion.button
                    whileHover={{ scale: 1.03 }}
                    whileTap={{ scale: 0.97 }}
                    onClick={handleComplete}
                    className="w-full py-3 rounded-xl bg-construct-accent-primary text-construct-bg-primary font-semibold text-sm btn-interactive"
                  >
                    Start Building
                  </motion.button>
                </div>
              )}
            </motion.div>
          </AnimatePresence>
        </div>

        {/* Footer: navigation */}
        {step < 4 && (
          <div className="px-8 pb-6">
            <div className="flex items-center justify-between">
              {/* Back button */}
              <button
                onClick={goBack}
                disabled={step === 0}
                className={`flex items-center gap-1 px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                  step === 0
                    ? "text-construct-text-muted/30 cursor-not-allowed"
                    : "text-construct-text-muted hover:text-construct-text-primary hover:bg-white/5"
                }`}
              >
                <ChevronLeft className="w-4 h-4" />
                Back
              </button>

              {/* Step indicators */}
              <div className="flex items-center gap-2">
                {Array.from({ length: totalSteps - 1 }).map((_, i) => (
                  <button
                    key={i}
                    onClick={() => {
                      setDirection(i > step ? 1 : -1);
                      setStep(i);
                    }}
                    className={`w-2 h-2 rounded-full transition-all ${
                      i === step
                        ? "w-6 bg-construct-accent-primary"
                        : i < step
                        ? "bg-construct-accent-primary/50"
                        : "bg-construct-border/50 hover:bg-construct-border"
                    }`}
                  />
                ))}
              </div>

              {/* Next button */}
              <button
                onClick={goNext}
                className="flex items-center gap-1 px-4 py-2 rounded-lg bg-construct-accent-primary/10 text-construct-accent-primary text-xs font-medium hover:bg-construct-accent-primary/20 transition-colors btn-interactive"
              >
                Next
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </motion.div>
    </div>
  );
};

export default OnboardingModal;
