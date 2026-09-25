import React from "react";
import { useCurrentFrame } from "remotion";
import { Background } from "../theme/Background";
import { TornPaper } from "../theme/Paper";
import { Tape } from "../theme/Overlays";
import { COLORS, FONTS } from "../theme/theme";
import { Reveal, riseIn } from "../theme/anim";

/** Small control-rod position schematic (initial vs inserted). */
const RodSchematic: React.FC = () => {
  const frame = useCurrentFrame();
  const shift = Math.min(1, frame / 50);
  return (
    <div
      style={{
        display: "flex",
        gap: 26,
        alignItems: "flex-end",
        opacity: riseIn(frame, 30, 12).opacity,
      }}
    >
      {["TRƯỚC", "SAU"].map((label, col) => (
        <div key={label} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
          <div style={{ position: "relative", width: 34, height: 120, border: `2px solid ${COLORS.line}`, background: "rgba(13,18,28,0.6)" }}>
            {/* rod */}
            <div
              style={{
                position: "absolute",
                left: 9,
                width: 14,
                top: col === 0 ? 16 : 16 + shift * 70,
                height: 34,
                background: "#5b6b82",
                border: "1px solid #202836",
              }}
            />
            {/* graphite tip */}
            <div
              style={{
                position: "absolute",
                left: 8,
                width: 16,
                top: col === 0 ? 50 : 50 + shift * 70,
                height: 18,
                background: "#3f4650",
              }}
            />
            {/* arrow */}
            {col === 1 && (
              <div style={{ position: "absolute", left: 42, top: 40 + shift * 70, color: COLORS.red, fontFamily: FONTS.mono, fontSize: 20 }}>
                ▼
              </div>
            )}
          </div>
          <div style={{ fontFamily: FONTS.mono, fontSize: 18, color: COLORS.muted, letterSpacing: "0.2em" }}>{label}</div>
        </div>
      ))}
    </div>
  );
};

const Panel: React.FC<{
  heading: string;
  items: string[];
  accent: string;
  delay: number;
  paperSeed: number;
}> = ({ heading, items, accent, delay, paperSeed }) => {
  return (
    <Reveal delay={delay} distance={70}>
      <div style={{ position: "relative" }}>
        <TornPaper width={640} height={640} seed={paperSeed} rotate={paperSeed === 11 ? -2 : 2}>
          <div style={{ padding: 28 }}>
            <div
              style={{
                fontFamily: FONTS.sans,
                fontWeight: 900,
                fontSize: 30,
                letterSpacing: "0.1em",
                textTransform: "uppercase",
                color: accent === COLORS.red ? COLORS.red : COLORS.ink,
                borderBottom: `4px solid ${accent}`,
                paddingBottom: 14,
                marginBottom: 26,
              }}
            >
              {heading}
            </div>
            {items.map((item, i) => (
              <Reveal key={i} delay={delay + 12 + i * 8} distance={26}>
                <div style={{ display: "flex", gap: 18, alignItems: "baseline", padding: "11px 0" }}>
                  <div
                    style={{
                      fontFamily: FONTS.mono,
                      fontSize: 26,
                      fontWeight: 700,
                      color: accent,
                      flexShrink: 0,
                    }}
                  >
                    {i + 1}.
                  </div>
                  <div style={{ fontFamily: FONTS.serif, fontSize: 31, color: COLORS.ink, lineHeight: 1.3 }}>{item}</div>
                </div>
              </Reveal>
            ))}
          </div>
        </TornPaper>
      </div>
    </Reveal>
  );
};

/**
 * Side-by-side comparison: "what should have happened" (calm panel)
 * vs "what actually happened" (red-accented panel), plus rod schematic.
 */
export const ComparisonScene: React.FC<{
  headingA: string;
  itemsA: string[];
  headingB: string;
  itemsB: string[];
  showSchematic?: boolean;
}> = ({ headingA, itemsA, headingB, itemsB, showSchematic = true }) => {
  return (
    <Background>
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 56,
          padding: "80px 110px",
        }}
      >
        {showSchematic && (
          <div style={{ flexShrink: 0, marginRight: 10 }}>
            <RodSchematic />
          </div>
        )}
        <Panel heading={headingA} items={itemsA} accent={COLORS.ink} delay={8} paperSeed={11} />
        <Panel heading={headingB} items={itemsB} accent={COLORS.red} delay={20} paperSeed={29} />
        <Tape width={130} height={38} rotate={-38} style={{ top: 40, left: "46%" }} />
      </div>
    </Background>
  );
};
