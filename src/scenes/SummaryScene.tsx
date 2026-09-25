import React from "react";
import { useCurrentFrame } from "remotion";
import { Background } from "../theme/Background";
import { COLORS, FONTS } from "../theme/theme";
import { Reveal, riseIn } from "../theme/anim";

/** Closing card: key takeaways, dossier style. */
export const SummaryScene: React.FC<{
  heading: string;
  points: string[];
}> = ({ heading, points }) => {
  const frame = useCurrentFrame();
  return (
    <Background>
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: "0 200px",
        }}
      >
        <Reveal delay={6}>
          <div
            style={{
              fontFamily: FONTS.display,
              fontSize: 84,
              color: COLORS.white,
              textTransform: "uppercase",
              letterSpacing: "0.03em",
              marginBottom: 20,
            }}
          >
            {heading}
          </div>
        </Reveal>

        <div
          style={{
            height: 5,
            width: 200,
            background: COLORS.red,
            marginBottom: 46,
            opacity: riseIn(frame, 14, 10).opacity,
          }}
        />

        {points.map((p, i) => (
          <Reveal key={i} delay={18 + i * 10} distance={40}>
            <div style={{ display: "flex", gap: 24, alignItems: "flex-start", padding: "13px 0" }}>
              <div
                style={{
                  fontFamily: FONTS.mono,
                  fontSize: 28,
                  color: COLORS.red,
                  flexShrink: 0,
                  marginTop: 6,
                }}
              >
                ■
              </div>
              <div
                style={{
                  fontFamily: FONTS.serif,
                  fontSize: 40,
                  color: COLORS.white,
                  lineHeight: 1.35,
                }}
              >
                {p}
              </div>
            </div>
          </Reveal>
        ))}
      </div>
    </Background>
  );
};
