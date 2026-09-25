import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { Background } from "../theme/Background";
import { TornPaper } from "../theme/Paper";
import { Tape } from "../theme/Overlays";
import { COLORS, FONTS } from "../theme/theme";
import { Reveal } from "../theme/anim";

/* ------------------------------------------------------------------ */
/* Hand-drawn style line chart on aged paper                           */
/* ------------------------------------------------------------------ */

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

/** Builds a wobbly hand-drawn polyline through the data points. */
function wobblyPath(
  pts: { x: number; y: number }[],
  seed: number,
  amp = 5,
): string {
  const rnd = mulberry32(seed);
  let d = `M ${pts[0].x} ${pts[0].y}`;
  for (let i = 1; i < pts.length; i++) {
    const p0 = pts[i - 1];
    const p1 = pts[i];
    const mx = (p0.x + p1.x) / 2;
    const my = (p0.y + p1.y) / 2;
    const jx = (rnd() - 0.5) * amp * 2;
    const jy = (rnd() - 0.5) * amp * 2;
    d += ` Q ${p0.x + (p1.x - p0.x) * 0.33 + jx} ${p0.y + (p1.y - p0.y) * 0.33 + jy}, ${mx} ${my}`;
    d += ` T ${p1.x} ${p1.y}`;
  }
  return d;
}

const HandChart: React.FC<{
  data: number[];
  xLabels: string[];
  yTicks: number[];
  annotation?: string;
  eventLabel?: string;
}> = ({ data, xLabels, yTicks, annotation, eventLabel }) => {
  const frame = useCurrentFrame();
  const W = 880;
  const H = 560;
  const padL = 90;
  const padR = 50;
  const padT = 60;
  const padB = 80;
  const plotW = W - padL - padR;
  const plotH = H - padT - padB;

  const yMax = Math.max(...yTicks);
  const pts = data.map((v, i) => ({
    x: padL + (i / (data.length - 1)) * plotW,
    y: padT + plotH - (v / yMax) * plotH,
  }));

  const draw = interpolate(frame, [15, 75], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const drawnPath = wobblyPath(pts, 5);

  const peakIdx = data.indexOf(Math.max(...data));
  const peak = pts[peakIdx];
  const annDelay = 80;

  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`}>
      {/* Axis lines */}
      <line x1={padL} y1={padT} x2={padL} y2={padT + plotH} stroke={COLORS.ink} strokeWidth="3" opacity="0.8" />
      <line x1={padL} y1={padT + plotH} x2={padL + plotW} y2={padT + plotH} stroke={COLORS.ink} strokeWidth="3" opacity="0.8" />

      {/* Y ticks */}
      {yTicks.map((t) => {
        const y = padT + plotH - (t / yMax) * plotH;
        return (
          <g key={t}>
            <line x1={padL - 8} y1={y} x2={padL} y2={y} stroke={COLORS.ink} strokeWidth="2" opacity="0.7" />
            <text x={padL - 16} y={y + 6} textAnchor="end" fontSize="22" fontFamily={FONTS.mono} fill={COLORS.ink} opacity="0.85">
              {t}
            </text>
            <line x1={padL} y1={y} x2={padL + plotW} y2={y} stroke={COLORS.ink} strokeWidth="1" opacity="0.18" strokeDasharray="5 7" />
          </g>
        );
      })}

      {/* X labels */}
      {xLabels.map((l, i) => (
        <text
          key={l + i}
          x={padL + (i / (xLabels.length - 1)) * plotW}
          y={H - 36}
          textAnchor="middle"
          fontSize="22"
          fontFamily={FONTS.mono}
          fill={COLORS.ink}
          opacity="0.85"
        >
          {l}
        </text>
      ))}

      {/* Grid label */}
      <text x={W / 2} y={padT - 22} textAnchor="middle" fontSize="26" fontFamily={FONTS.sans} fontWeight={700} fill={COLORS.ink} letterSpacing="2">
        {yTicks.length ? `${Math.max(...yTicks)} MW` : ""}
      </text>

      {/* The line (revealed via clip-path for draw-on effect) */}
      <defs>
        <clipPath id="drawClip">
          <rect x={0} y={0} width={padL + plotW * draw + 20} height={H} />
        </clipPath>
      </defs>
      <g clipPath="url(#drawClip)">
        <path d={drawnPath} fill="none" stroke={COLORS.red} strokeWidth="5" strokeLinecap="round" />
        <path d={drawnPath} fill="none" stroke="rgba(196,61,47,0.25)" strokeWidth="12" strokeLinecap="round" />
      </g>

      {/* Peak marker + annotation */}
      {draw >= 0.99 && (
        <g opacity={interpolate(frame, [annDelay, annDelay + 12], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })}>
          <circle cx={peak.x} cy={peak.y} r={10} fill={COLORS.red} stroke={COLORS.white} strokeWidth="3" />
          <path
            d={`M ${peak.x - 40} ${peak.y - 70} q 40 30 30 62`}
            fill="none"
            stroke={COLORS.red}
            strokeWidth="3"
          />
          <text x={peak.x - 210} y={peak.y - 86} fontSize="24" fontFamily={FONTS.mono} fill={COLORS.red} fontWeight="700">
            {annotation ?? "Power spikes"}
          </text>
          {eventLabel && (
            <g>
              <rect x={peak.x - 250} y={peak.y + 26} width={230} height={44} fill={COLORS.red} />
              <text x={peak.x - 135} y={peak.y + 55} textAnchor="middle" fontSize="21" fontFamily={FONTS.sans} fontWeight={900} fill={COLORS.white} letterSpacing="1">
                {eventLabel}
              </text>
            </g>
          )}
        </g>
      )}
    </svg>
  );
};

/* ------------------------------------------------------------------ */
/* Scene                                                               */
/* ------------------------------------------------------------------ */

/** Hand-drawn power chart taped onto the board. */
export const ChartScene: React.FC<{
  heading: string;
  data: number[];
  xLabels: string[];
  yTicks: number[];
  annotation?: string;
  eventLabel?: string;
}> = ({ heading, data, xLabels, yTicks, annotation, eventLabel }) => {
  return (
    <Background>
      <div style={{ position: "absolute", inset: 0, padding: "84px 130px 120px" }}>
        <Reveal delay={4}>
          <div
            style={{
              fontFamily: FONTS.sans,
              fontSize: 28,
              letterSpacing: "0.34em",
              color: COLORS.muted,
              textTransform: "uppercase",
              marginBottom: 36,
            }}
          >
            {heading}
          </div>
        </Reveal>

        <Reveal delay={10} distance={80}>
          <div style={{ position: "relative", width: 980, height: 660 }}>
            <TornPaper width={980} height={660} seed={17} rotate={-1}>
              <div style={{ padding: 24 }}>
                <HandChart
                  data={data}
                  xLabels={xLabels}
                  yTicks={yTicks}
                  annotation={annotation}
                  eventLabel={eventLabel}
                />
              </div>
            </TornPaper>
            <Tape width={130} height={38} rotate={-40} style={{ top: -16, left: 90 }} />
            <Tape width={130} height={38} rotate={42} style={{ bottom: -14, left: 640 }} />
          </div>
        </Reveal>
      </div>
    </Background>
  );
};
