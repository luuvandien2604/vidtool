import React from "react";
import { COLORS } from "./theme";

/**
 * Dark archival background: deep navy with blueprint grid,
 * vignette, grain and corner registration marks.
 */
export const Background: React.FC<{ children?: React.ReactNode }> = ({
  children,
}) => {
  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        background: `radial-gradient(ellipse at 50% 40%, ${COLORS.bg} 0%, ${COLORS.bgDeep} 100%)`,
        overflow: "hidden",
      }}
    >
      {/* Blueprint grid */}
      <svg
        style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}
      >
        <defs>
          <pattern
            id="bpGrid"
            width="64"
            height="64"
            patternUnits="userSpaceOnUse"
          >
            <path
              d="M 64 0 L 0 0 0 64"
              fill="none"
              stroke={COLORS.grid}
              strokeWidth="1"
            />
          </pattern>
          <pattern
            id="bpGridLarge"
            width="256"
            height="256"
            patternUnits="userSpaceOnUse"
          >
            <path
              d="M 256 0 L 0 0 0 256"
              fill="none"
              stroke={COLORS.gridStrong}
              strokeWidth="1"
            />
          </pattern>
          <filter id="grain">
            <feTurbulence
              type="fractalNoise"
              baseFrequency="0.9"
              numOctaves="2"
              stitchTiles="stitch"
              result="n"
            />
            <feColorMatrix
              in="n"
              type="matrix"
              values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 0.05 0"
            />
          </filter>
        </defs>
        <rect width="100%" height="100%" fill="url(#bpGridLarge)" />
        <rect width="100%" height="100%" fill="url(#bpGrid)" />
      </svg>

      {/* Vignette */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,0.55) 100%)",
        }}
      />
      {/* Grain */}
      <svg
        style={{
          position: "absolute",
          inset: 0,
          width: "100%",
          height: "100%",
          opacity: 0.5,
        }}
      >
        <rect width="100%" height="100%" filter="url(#grain)" />
      </svg>

      {/* Corner registration marks */}
      {[
        { top: 24, left: 24 },
        { top: 24, right: 24 },
        { bottom: 24, left: 24 },
        { bottom: 24, right: 24 },
      ].map((pos, i) => (
        <svg
          key={i}
          width="26"
          height="26"
          viewBox="0 0 26 26"
          style={{ position: "absolute", opacity: 0.5, ...pos }}
        >
          <path
            d="M 1 14 L 1 1 L 14 1"
            fill="none"
            stroke={COLORS.muted}
            strokeWidth="1.5"
          />
        </svg>
      ))}

      {children}
    </div>
  );
};
