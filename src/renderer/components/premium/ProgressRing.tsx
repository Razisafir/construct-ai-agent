interface ProgressBarProps {
  progress: number;
  width?: number;
  showPercent?: boolean;
}

export function ProgressRing({
  progress,
  width = 20,
  showPercent = true,
}: ProgressBarProps) {
  const clamped = Math.max(0, Math.min(100, progress));
  const filled = Math.round((clamped / 100) * width);
  const empty = width - filled;

  const bar = "█".repeat(filled) + "░".repeat(empty);

  return (
    <span
      className="inline-flex items-center gap-2 font-mono text-[10px] whitespace-pre"
    >
      <span className="text-accent-cyan">{bar}</span>
      {showPercent && (
        <span className="text-text-primary text-[10px]">
          {Math.round(clamped)}%
        </span>
      )}
    </span>
  );
}
