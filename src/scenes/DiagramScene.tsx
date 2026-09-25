import React from "react";
import { useCurrentFrame } from "remotion";
import { Background } from "../theme/Background";
import { Tape } from "../theme/Overlays";
import { COLORS, FONTS } from "../theme/theme";
import { Reveal, fadeIn } from "../theme/anim";

type Callout = { label: string; description?: string; x: number; y: number };
type Kind = "reactor" | "flow" | "stack";

/* ------------------------------------------------------------------ */
/* Diagram drawings (SVG)                                              */
/* ------------------------------------------------------------------ */

const ReactorDiagram: React.FC<{ nodes: Callout[] }> = ({ nodes }) => {
  const frame = useCurrentFrame();
  const W = 620;
  const H = 640;
  // Core glow pulse
  const pulse = 0.75 + 0.25 * Math.sin(frame / 6);
  // Rods descend slowly then hold
  const rodShift = Math.min(1, frame / 90) * 90;
  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`}>
      <defs>
        <radialGradient id="coreGlow" cx="0.5" cy="0.5" r="0.6">
          <stop offset="0%" stopColor="#ffb347" />
          <stop offset="60%" stopColor="#e5533f" />
          <stop offset="100%" stopColor="#7a1f14" />
        </radialGradient>
        <filter id="coreBlur">
          <feGaussianBlur stdDeviation="14" />
        </filter>
      </defs>

      {/* Top cap / steam separator */}
      <rect x={180} y={30} width={260} height={110} rx={16} fill="#1d242e" stroke="#54627a" strokeWidth="3" />
      <line x1={200} y1={30} x2={200} y2={140} stroke="#54627a" strokeWidth="1.5" opacity="0.5" />
      <line x1={240} y1={30} x2={240} y2={140} stroke="#54627a" strokeWidth="1.5" opacity="0.5" />
      <line x1={280} y1={30} x2={280} y2={140} stroke="#54627a" strokeWidth="1.5" opacity="0.5" />
      <line x1={320} y1={30} x2={320} y2={140} stroke="#54627a" strokeWidth="1.5" opacity="0.5" />
      <line x1={360} y1={30} x2={360} y2={140} stroke="#54627a" strokeWidth="1.5" opacity="0.5" />
      <line x1={400} y1={30} x2={400} y2={140} stroke="#54627a" strokeWidth="1.5" opacity="0.5" />
      <text x={310} y={100} textAnchor="middle" fill="#8b98ad" fontSize="22" fontFamily={FONTS.mono} letterSpacing="3">
        CHANNEL HEAD
      </text>

      {/* Pipes */}
      <rect x={150} y={48} width={30} height={18} fill="#2a3442" stroke="#54627a" strokeWidth="2" />
      <rect x={440} y={48} width={30} height={18} fill="#2a3442" stroke="#54627a" strokeWidth="2" />
      <rect x={150} y={96} width={30} height={18} fill="#2a3442" stroke="#54627a" strokeWidth="2" />
      <rect x={440} y={96} width={30} height={18} fill="#2a3442" stroke="#54627a" strokeWidth="2" />

      {/* Control rods (descend during scene) */}
      {Array.from({ length: 7 }).map((_, i) => {
        const x = 228 + i * 34;
        const depth = Math.max(0, rodShift - i * 0.08) * (200 + (i % 3) * 40);
        return (
          <g key={i}>
            {/* Rod shaft */}
            <rect x={x - 6} y={150} width={12} height={Math.min(210, 60 + depth)} fill="#5b6b82" stroke="#202836" strokeWidth="2" />
            {/* Graphite tip */}
            <rect
              x={x - 7}
              y={150 + Math.min(210, 60 + depth) - 26}
              width={14}
              height={26}
              fill="#3f4650"
              stroke="#1c222c"
              strokeWidth="2"
            />
            {/* Position indicator */}
            <circle cx={x} cy={146} r={5} fill={frame > 60 ? COLORS.red : "#8a9aad"} />
          </g>
        );
      })}

      {/* Vessel */}
      <rect x={170} y={170} width={280} height={430} rx={30} fill="#161d27" stroke="#54627a" strokeWidth="4" />

      {/* Core */}
      <ellipse cx={310} cy={385} rx={118} ry={150} fill="url(#coreGlow)" filter="url(#coreBlur)" opacity={pulse} />
      <ellipse cx={310} cy={385} rx={92} ry={122} fill="url(#coreGlow)" />
      {/* Fuel channels grid */}
      {Array.from({ length: 9 }).map((_, row) =>
        Array.from({ length: 5 }).map((_, col) => (
          <rect
            key={`${row}-${col}`}
            x={248 + col * 26}
            y={288 + row * 24}
            width={14}
            height={14}
            rx={3}
            fill={row % 3 === 0 ? "#e5533f" : "#c98f2d"}
            opacity={0.85 + 0.15 * Math.sin(frame / 5 + row + col)}
          />
        )),
      )}

      {/* Vessel label */}
      <text x={310} y={600} textAnchor="middle" fill="#8b98ad" fontSize="22" fontFamily={FONTS.mono} letterSpacing="3">
        RBMK-1000 · CORE
      </text>

      {/* Base */}
      <rect x={210} y={602} width={200} height={26} rx={8} fill="#1d242e" stroke="#54627a" strokeWidth="3" />
    </svg>
  );
};

const FlowDiagram: React.FC = () => {
  const frame = useCurrentFrame();
  const on = Math.min(1, frame / 40);
  return (
    <svg width={620} height={400} viewBox="0 0 620 400">
      {[0, 1, 2].map((i) => (
        <g key={i}>
          <rect
            x={60 + i * 210}
            y={150}
            width={140}
            height={100}
            rx={10}
            fill="#1d242e"
            stroke={i === 1 ? COLORS.red : "#54627a"}
            strokeWidth="4"
          />
          <text x={130 + i * 210} y={206} textAnchor="middle" fill="#f2efe6" fontSize="24" fontFamily={FONTS.sans}>
            {["INPUT", "PROCESS", "OUTPUT"][i]}
          </text>
          {i < 2 && (
            <g>
              <line
                x1={200 + i * 210}
                y1={200}
                x2={270 + i * 210}
                y2={200}
                stroke={COLORS.red}
                strokeWidth="4"
                strokeDasharray="8 6"
              />
              <path
                d={`M ${262 + i * 210} 190 L ${280 + i * 210} 200 L ${262 + i * 210} 210`}
                fill="none"
                stroke={COLORS.red}
                strokeWidth="4"
              />
              <circle cx={200 + i * 210 + 70 * on} cy={200} r={5} fill={COLORS.redBright} />
            </g>
          )}
        </g>
      ))}
    </svg>
  );
};

const StackDiagram: React.FC = () => {
  const frame = useCurrentFrame();
  const bars = [180, 300, 420, 260];
  return (
    <svg width={620} height={420} viewBox="0 0 620 420">
      {bars.map((h, i) => (
        <rect
          key={i}
          x={90 + i * 120}
          y={380 - h * Math.min(1, frame / (30 + i * 12))}
          width={70}
          height={h * Math.min(1, frame / (30 + i * 12))}
          fill={i === bars.length - 1 ? COLORS.red : "#3d4d63"}
          stroke="#202836"
          strokeWidth="3"
        />
      ))}
      <line x1={60} y1={380} x2={580} y2={380} stroke="#54627a" strokeWidth="3" />
    </svg>
  );
};

/* ------------------------------------------------------------------ */
/* Scene                                                               */
/* ------------------------------------------------------------------ */

/**
 * Technical diagram scene: machine drawing on the left (taped),
 * callout labels on the right with red connectors.
 */
export const DiagramScene: React.FC<{
  heading: string;
  kind: Kind;
  caption?: string;
  nodes: Callout[];
}> = ({ heading, kind, caption, nodes }) => {
  const frame = useCurrentFrame();
  const Diagram = kind === "reactor" ? ReactorDiagram : kind === "flow" ? FlowDiagram : StackDiagram;
  return (
    <Background>
      <div style={{ position: "absolute", inset: 0, padding: "90px 120px 110px" }}>
        <Reveal delay={4}>
          <div
            style={{
              fontFamily: FONTS.sans,
              fontSize: 28,
              letterSpacing: "0.34em",
              color: COLORS.muted,
              textTransform: "uppercase",
              marginBottom: 8,
            }}
          >
            {heading}
          </div>
        </Reveal>

        <div style={{ display: "flex", gap: 90, alignItems: "flex-start", marginTop: 40 }}>
          {/* Left: diagram on a subtle plate, taped */}
          <Reveal delay={10} distance={60}>
            <div
              style={{
                position: "relative",
                width: 640,
                height: 660,
                background: "rgba(13,18,28,0.55)",
                border: "1px solid rgba(242,239,230,0.14)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                padding: 10,
              }}
            >
              <Diagram nodes={nodes} />
              <Tape width={110} height={34} rotate={-42} style={{ top: -14, left: 60 }} />
              <Tape width={110} height={34} rotate={38} style={{ top: -12, right: 80 }} />
            </div>
          </Reveal>

          {/* Right: callouts */}
          <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 34, paddingTop: 30 }}>
            {nodes.map((n, i) => (
              <Reveal key={i} delay={22 + i * 12} distance={50}>
                <div
                  style={{
                    position: "relative",
                    background: COLORS.white,
                    color: COLORS.black,
                    border: `3px solid ${COLORS.black}`,
                    boxShadow: "6px 6px 0 rgba(0,0,0,0.45)",
                    padding: "18px 24px",
                  }}
                >
                  <div
                    style={{
                      fontFamily: FONTS.sans,
                      fontWeight: 900,
                      fontSize: 26,
                      letterSpacing: "0.16em",
                      textTransform: "uppercase",
                    }}
                  >
                    {n.label}
                  </div>
                  {n.description && (
                    <div
                      style={{
                        fontFamily: FONTS.serif,
                        fontSize: 25,
                        marginTop: 8,
                        color: "#3a332a",
                        lineHeight: 1.35,
                      }}
                    >
                      {n.description}
                    </div>
                  )}
                </div>
              </Reveal>
            ))}
          </div>
        </div>

        {caption && (
          <div
            style={{
              position: "absolute",
              bottom: 90,
              left: 120,
              fontFamily: FONTS.mono,
              fontSize: 22,
              color: COLORS.muted,
              letterSpacing: "0.18em",
              opacity: fadeIn(frame, 30, 14),
            }}
          >
            {caption}
          </div>
        )}
      </div>
    </Background>
  );
};
