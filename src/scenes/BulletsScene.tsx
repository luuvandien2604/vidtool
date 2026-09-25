import React from "react";
import { Background } from "../theme/Background";
import { COLORS, FONTS } from "../theme/theme";
import { Reveal } from "../theme/anim";

/** Numbered briefing list on dark board, dossier style. */
export const BulletsScene: React.FC<{
  heading: string;
  items: string[];
  numbered?: boolean;
}> = ({ heading, items, numbered = true }) => {
  return (
    <Background>
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: "0 170px",
        }}
      >
        <Reveal delay={6}>
          <div
            style={{
              fontFamily: FONTS.sans,
              fontSize: 30,
              fontWeight: 700,
              letterSpacing: "0.36em",
              color: COLORS.red,
              textTransform: "uppercase",
              marginBottom: 46,
            }}
          >
            ▍{heading}
          </div>
        </Reveal>

        {items.map((item, i) => (
          <Reveal key={i} delay={16 + i * 9} distance={44}>
            <div
              style={{
                display: "flex",
                alignItems: "baseline",
                gap: 28,
                padding: "16px 0",
                borderBottom: "1px solid rgba(242,239,230,0.10)",
              }}
            >
              {numbered && (
                <div
                  style={{
                    fontFamily: FONTS.mono,
                    fontSize: 30,
                    color: COLORS.red,
                    width: 56,
                    flexShrink: 0,
                    letterSpacing: "0.1em",
                  }}
                >
                  {String(i + 1).padStart(2, "0")}
                </div>
              )}
              <div
                style={{
                  fontFamily: FONTS.serif,
                  fontSize: 44,
                  color: COLORS.white,
                  lineHeight: 1.25,
                }}
              >
                {item}
              </div>
            </div>
          </Reveal>
        ))}
      </div>
    </Background>
  );
};
