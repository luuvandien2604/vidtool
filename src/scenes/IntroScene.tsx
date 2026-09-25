import React from "react";
import { useCurrentFrame, useVideoConfig } from "remotion";
import { Background } from "../theme/Background";
import { HazardSymbol } from "../theme/Overlays";
import { COLORS, FONTS } from "../theme/theme";
import { Reveal, riseIn, popIn, useSceneProgress } from "../theme/anim";

/**
 * Opening title card, mirroring the reference: kicker + heavy title,
 * red rule, date/time in mono, hazard mark top-right.
 */
export const IntroScene: React.FC<{
  kicker: string;
  title: string;
  subtitle: string;
  date?: string;
  time?: string;
  hazard?: boolean;
}> = ({ kicker, title, subtitle, date, time, hazard = true }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const progress = useSceneProgress();

  // Slow Ken Burns drift on the whole board.
  const drift = Math.sin(progress * Math.PI) * 6;

  return (
    <Background>
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: "0 150px",
          transform: `translateY(${drift}px)`,
        }}
      >
        {/* Kicker */}
        <Reveal delay={6}>
          <div
            style={{
              fontFamily: FONTS.sans,
              fontSize: 34,
              fontWeight: 700,
              letterSpacing: "0.42em",
              color: COLORS.muted,
              textTransform: "uppercase",
            }}
          >
            {kicker}
          </div>
        </Reveal>

        {/* Title */}
        <div style={{ height: 30 }} />
        <Reveal delay={14}>
          <div
            style={{
              fontFamily: FONTS.display,
              fontSize: 128,
              lineHeight: 1.02,
              color: COLORS.white,
              textTransform: "uppercase",
              letterSpacing: "0.02em",
              textShadow: "0 6px 0 rgba(0,0,0,0.35)",
            }}
          >
            {title}
          </div>
        </Reveal>

        {/* Subtitle */}
        <div style={{ height: 22 }} />
        <Reveal delay={24}>
          <div
            style={{
              fontFamily: FONTS.serif,
              fontStyle: "italic",
              fontSize: 40,
              color: COLORS.muted,
            }}
          >
            {subtitle}
          </div>
        </Reveal>

        {/* Red rule */}
        <div style={{ height: 34 }} />
        <div
          style={{
            height: 6,
            background: COLORS.red,
            // grows in from the left
            width: `${Math.min(100, Math.max(0, (frame - 26) * 3))}%`,
            maxWidth: 420,
            boxShadow: `0 0 18px ${COLORS.redBright}66`,
          }}
        />

        {/* Date / time strip */}
        {(date || time) && (
          <div style={{ height: 30 }} />
        )}
        <Reveal delay={36}>
          <div style={{ display: "flex", gap: 30, alignItems: "baseline" }}>
            {time && (
              <div
                style={{
                  fontFamily: FONTS.mono,
                  fontSize: 34,
                  color: COLORS.white,
                  letterSpacing: "0.18em",
                }}
              >
                {time}
              </div>
            )}
            {date && (
              <div
                style={{
                  fontFamily: FONTS.mono,
                  fontSize: 30,
                  color: COLORS.muted,
                  letterSpacing: "0.22em",
                  textTransform: "uppercase",
                }}
              >
                {date}
              </div>
            )}
          </div>
        </Reveal>
      </div>

      {/* Hazard mark, top-right */}
      {hazard && (
        <div
          style={{
            position: "absolute",
            top: 54,
            right: 60,
            transform: `scale(${popIn(frame, 30, fps)})`,
            opacity: riseIn(frame, 28, 8).opacity,
          }}
        >
          <HazardSymbol size={86} />
        </div>
      )}

      {/* Top-left file tag */}
      <div
        style={{
          position: "absolute",
          top: 50,
          left: 60,
          fontFamily: FONTS.mono,
          fontSize: 22,
          color: COLORS.muted,
          letterSpacing: "0.28em",
          opacity: riseIn(frame, 20, 10).opacity,
        }}
      >
        ARCHIVE // DOC-{String(Math.floor(frame / fps) + 1986).padStart(4, "0")}
      </div>
    </Background>
  );
};
