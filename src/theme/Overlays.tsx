import React from "react";
import { COLORS } from "./theme";

/** Translucent adhesive tape strip used to "pin" items on the board. */
export const Tape: React.FC<{
  width?: number;
  height?: number;
  rotate?: number;
  style?: React.CSSProperties;
}> = ({ width = 90, height = 30, rotate = -45, style }) => {
  return (
    <div
      style={{
        width,
        height,
        position: "absolute",
        background: `linear-gradient(100deg, ${COLORS.tape} 0%, rgba(240,235,215,0.22) 55%, ${COLORS.tape} 100%)`,
        border: "1px solid rgba(255,255,255,0.12)",
        transform: `rotate(${rotate}deg)`,
        boxShadow: "0 2px 6px rgba(0,0,0,0.35)",
        zIndex: 30,
        ...style,
      }}
    />
  );
};

/** Red rubber stamp, slightly rotated, distressed feel. */
export const Stamp: React.FC<{
  text: string;
  sub?: string;
  width?: number;
  rotate?: number;
  color?: string;
  style?: React.CSSProperties;
}> = ({ text, sub, width = 220, rotate = -7, color = COLORS.red, style }) => {
  return (
    <div
      style={{
        width,
        padding: "12px 16px",
        border: `4px double ${color}`,
        borderRadius: 3,
        textAlign: "center",
        transform: `rotate(${rotate}deg)`,
        opacity: 0.92,
        boxShadow: `inset 0 0 8px rgba(0,0,0,0.25)`,
        ...style,
      }}
    >
      <div
        style={{
          fontFamily: "Impact, 'Arial Black', sans-serif",
          fontSize: width * 0.16,
          letterSpacing: "0.12em",
          color,
          textTransform: "uppercase",
          lineHeight: 1.15,
          filter: "url(#stampRough)",
        }}
      >
        {text}
      </div>
      {sub ? (
        <div
          style={{
            fontFamily: "Courier New, monospace",
            fontSize: width * 0.075,
            letterSpacing: "0.18em",
            color,
            marginTop: 4,
          }}
        >
          {sub}
        </div>
      ) : null}
    </div>
  );
};

/** Radiation trefoil symbol, yellow on dark disc. */
export const HazardSymbol: React.FC<{
  size?: number;
  style?: React.CSSProperties;
}> = ({ size = 64, style }) => {
  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: "50%",
        background: COLORS.black,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        boxShadow: "0 0 0 2px rgba(255,255,255,0.15)",
        ...style,
      }}
    >
      <svg width={size * 0.72} height={size * 0.72} viewBox="0 0 100 100">
        <g fill="#e5c429">
          <circle cx="50" cy="50" r="12" />
          {[0, 120, 240].map((rot) => (
            <path
              key={rot}
              d="M 50 50 L 58 8 A 50 50 0 0 1 76 22 Z"
              transform={`rotate(${rot} 50 50)`}
            />
          ))}
        </g>
        <circle cx="50" cy="50" r="44" fill="none" stroke="#e5c429" strokeWidth="4" />
      </svg>
    </div>
  );
};

/** Bottom caption bar: narration text in mono, documentary style. */
export const CaptionBar: React.FC<{ text: string; style?: React.CSSProperties }> = ({
  text,
  style,
}) => {
  return (
    <div
      style={{
        position: "absolute",
        left: 120,
        right: 120,
        bottom: 42,
        zIndex: 20,
        ...style,
      }}
    >
      <div
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 14,
          background: "rgba(5,7,12,0.82)",
          border: "1px solid rgba(242,239,230,0.16)",
          borderLeft: `4px solid ${COLORS.red}`,
          padding: "12px 22px",
        }}
      >
        <div
          style={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            background: COLORS.red,
            flexShrink: 0,
          }}
        />
        <div
          style={{
            fontFamily: "'Courier New', Menlo, monospace",
            fontSize: 30,
            color: COLORS.white,
            letterSpacing: "0.04em",
            lineHeight: 1.35,
          }}
        >
          {text}
        </div>
      </div>
    </div>
  );
};
