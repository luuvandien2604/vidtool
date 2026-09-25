import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";

/** Opacity 0→1 ramp starting at `delay` frames, over `dur` frames. */
export function fadeIn(
  frame: number,
  delay: number,
  dur: number,
): number {
  return interpolate(frame, [delay, delay + dur], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
}

/** Translate + fade reveal (enters from below). */
export function riseIn(
  frame: number,
  delay: number,
  dur: number,
  distance = 36,
): { opacity: number; translateY: number } {
  return {
    opacity: fadeIn(frame, delay, dur),
    translateY: interpolate(frame, [delay, delay + dur], [distance, 0], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }),
  };
}

/** Spring pop-in scale (for stamps, badges). */
export function popIn(frame: number, delay: number, fps: number): number {
  return spring({ frame: frame - delay, fps, config: { damping: 12, mass: 0.7, stiffness: 140 } });
}

/**
 * Wrapper that reveals children with a delayed rise+fade,
 * used to stagger list items / callouts.
 */
export const Reveal: React.FC<{
  delay: number;
  distance?: number;
  dur?: number;
  children: React.ReactNode;
  style?: React.CSSProperties;
}> = ({ delay, distance = 36, dur = 14, children, style }) => {
  const frame = useCurrentFrame();
  const a = riseIn(frame, delay, dur, distance);
  return (
    <div
      style={{
        opacity: a.opacity,
        transform: `translateY(${a.translateY}px)`,
        ...style,
      }}
    >
      {children}
    </div>
  );
};

/** Progress helper: how far through this scene we are (0..1). */
export function useSceneProgress(): number {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  return interpolate(frame, [0, durationInFrames - 1], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
}
