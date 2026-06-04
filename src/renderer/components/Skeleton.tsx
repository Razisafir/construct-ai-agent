import React from "react";

interface SkeletonLineProps {
  width?: string;
  height?: string;
}

export const SkeletonLine: React.FC<SkeletonLineProps> = ({
  width = "100%",
  height = "12px",
}) => {
  return (
    <div
      className="rounded-none"
      style={{ width, height, background: "var(--c-s2)" }}
    />
  );
};

interface SkeletonBlockProps {
  width?: string;
  height?: string;
}

export const SkeletonBlock: React.FC<SkeletonBlockProps> = ({
  width = "100%",
  height = "80px",
}) => {
  return (
    <div
      className="rounded-none"
      style={{ width, height, background: "var(--c-s2)" }}
    />
  );
};

interface SkeletonCircleProps {
  size?: string;
}

export const SkeletonCircle: React.FC<SkeletonCircleProps> = ({
  size = "32px",
}) => {
  return (
    <div
      className="rounded-full"
      style={{ width: size, height: size, background: "var(--c-s2)" }}
    />
  );
};

interface SkeletonTextProps {
  lines?: number;
  lineHeight?: string;
  lastLineWidth?: string;
}

export const SkeletonText: React.FC<SkeletonTextProps> = ({
  lines = 3,
  lineHeight = "12px",
  lastLineWidth = "60%",
}) => {
  return (
    <div className="flex flex-col gap-1.5">
      {Array.from({ length: lines }).map((_, i) => (
        <SkeletonLine
          key={i}
          height={lineHeight}
          width={i === lines - 1 ? lastLineWidth : "100%"}
        />
      ))}
    </div>
  );
};

export const SkeletonCard: React.FC = () => {
  return (
    <div className="p-3 flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <SkeletonCircle size="32px" />
        <div className="flex-1 flex flex-col gap-1.5">
          <SkeletonLine width="60%" height="12px" />
          <SkeletonLine width="40%" height="10px" />
        </div>
      </div>
      <SkeletonText lines={2} lineHeight="12px" lastLineWidth="80%" />
    </div>
  );
};

export default {
  Line: SkeletonLine,
  Block: SkeletonBlock,
  Circle: SkeletonCircle,
  Text: SkeletonText,
  Card: SkeletonCard,
};
