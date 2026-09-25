import React from "react";
import { COLORS } from "./theme";

/** Deterministic pseudo-random from a seed. */
function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * Builds a torn-paper polygon path. The "torn" sides are top and bottom
 * by default; `tornSides` can pick which edges are jagged.
 */
function tornPath(
  w: number,
  h: number,
  seed: number,
  jag: number,
  tornSides: ("top" | "right" | "bottom" | "left")[],
): string {
  const rnd = mulberry32(seed);
  const N = 14;
  const jitter = (i: number) =>
    tornSides.includes("top") ? jag * (0.35 + 0.65 * rnd()) * (i % 2 ? 1 : -1) : 0;
  const jitterB = (i: number) =>
    tornSides.includes("bottom")
      ? jag * (0.35 + 0.65 * rnd()) * (i % 2 ? -1 : 1)
      : 0;
  const jitterL = (i: number) =>
    tornSides.includes("left") ? jag * (0.35 + 0.65 * rnd()) * (i % 2 ? 1 : -1) : 0;
  const jitterR = (i: number) =>
    tornSides.includes("right") ? jag * (0.35 + 0.65 * rnd()) * (i % 2 ? -1 : 1) : 0;

  let d = `M 0 ${jitter(0)}`;
  for (let i = 1; i <= N; i++) {
    const x = (w / N) * i;
    d += ` L ${x} ${jitter(i)}`;
  }
  d += ` L ${w} ${jitterR(0)}`;
  for (let i = 1; i <= N; i++) {
    const y = (h / N) * i;
    d += ` L ${w} ${y + jitterR(i)}`;
  }
  d += ` L ${w} ${h + jitterB(0)}`;
  for (let i = 1; i <= N; i++) {
    const x = w - (w / N) * i;
    d += ` L ${x} ${h + jitterB(i)}`;
  }
  d += ` L 0 ${h + jitterL(N)}`;
  for (let i = N; i >= 1; i--) {
    const y = (h / N) * i;
    d += ` L 0 ${y + jitterL(i)}`;
  }
  d += " Z";
  return d;
}

/**
 * Aged torn paper sheet. Optional rotation, drop shadow and inner shading.
 */
export const TornPaper: React.FC<{
  width: number;
  height: number;
  seed?: number;
  rotate?: number;
  tornSides?: ("top" | "right" | "bottom" | "left")[];
  children?: React.ReactNode;
  style?: React.CSSProperties;
}> = ({
  width,
  height,
  seed = 7,
  rotate = 0,
  tornSides = ["top", "bottom", "left", "right"],
  children,
  style,
}) => {
  const path = React.useMemo(
    () => tornPath(width, height, seed, Math.min(width, height) * 0.018, tornSides),
    [width, height, seed, tornSides],
  );
  return (
    <div
      style={{
        width,
        height,
        position: "relative",
        transform: rotate ? `rotate(${rotate}deg)` : undefined,
        filter: "drop-shadow(0 10px 24px rgba(0,0,0,0.55))",
        ...style,
      }}
    >
      <svg
        width={width}
        height={height}
        style={{ position: "absolute", inset: 0 }}
        viewBox={`0 0 ${width} ${height}`}
      >
        <defs>
          <linearGradient id={`paperShade${seed}`} x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor={COLORS.paper} />
            <stop offset="55%" stopColor={COLORS.paperDark} />
            <stop offset="100%" stopColor={COLORS.paperEdge} />
          </linearGradient>
          <radialGradient id={`paperStain${seed}`} cx="0.5" cy="0.4" r="0.8">
            <stop offset="0%" stopColor="rgba(60,45,20,0.0)" />
            <stop offset="75%" stopColor="rgba(60,45,20,0.10)" />
            <stop offset="100%" stopColor="rgba(60,45,20,0.28)" />
          </radialGradient>
        </defs>
        <path d={path} fill={`url(#paperShade${seed})`} stroke={COLORS.paperEdge} strokeWidth="1" />
        <path d={path} fill={`url(#paperStain${seed})`} />
        {/* Fibre streaks */}
        {Array.from({ length: 6 }).map((_, i) => (
          <line
            key={i}
            x1={width * 0.08 + i * 14}
            y1={0}
            x2={width * 0.16 + i * 17}
            y2={height}
            stroke="rgba(90,70,40,0.10)"
            strokeWidth="1.4"
          />
        ))}
      </svg>
      <div
        style={{
          position: "absolute",
          inset: 14,
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
        }}
      >
        {children}
      </div>
    </div>
  );
};
