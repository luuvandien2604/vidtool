import React from "react";
import { Img, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { Background } from "../theme/Background";
import { Tape, Stamp } from "../theme/Overlays";
import { COLORS, FONTS } from "../theme/theme";
import { Reveal, popIn } from "../theme/anim";

/**
 * Monochrome silhouette of a power plant, used when no photo
 * asset is supplied — keeps the scene fully offline.
 */
const SiteSilhouette: React.FC = () => (
  <svg width="860" height="470" viewBox="0 0 860 470">
    <defs>
      <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stopColor="#3a4048" />
        <stop offset="100%" stopColor="#171a20" />
      </linearGradient>
    </defs>
    <rect width="860" height="470" fill="url(#sky)" />
    {/* smokestack */}
    <rect x="600" y="70" width="90" height="260" fill="#0d0f13" />
    <rect x="590" y="50" width="110" height="26" fill="#0d0f13" />
    {/* tower block */}
    <rect x="180" y="170" width="330" height="160" fill="#12151b" />
    {Array.from({ length: 6 }).map((_, i) => (
      <rect key={i} x={200 + i * 50} y={190} width={24} height={34} fill="#1d232c" />
    ))}
    {Array.from({ length: 6 }).map((_, i) => (
      <rect key={`b${i}`} x={200 + i * 50} y={240} width={24} height={34} fill="#1d232c" />
    ))}
    {/* reactor tower */}
    <rect x="430" y="60" width="150" height="270" fill="#0f1217" />
    <rect x="470" y="100" width="70" height="120" fill="#181d25" />
    {/* cooling pond */}
    <rect x="0" y="330" width="860" height="140" fill="#0c0e12" />
    <ellipse cx="430" cy="330" rx="380" ry="26" fill="#151922" />
    {/* smoke */}
    <ellipse cx="645" cy="40" rx="34" ry="16" fill="#3c4149" opacity="0.7" />
    <ellipse cx="670" cy="18" rx="44" ry="18" fill="#33383f" opacity="0.5" />
  </svg>
);

/**
 * Site photo with red rubber stamp and tape corners.
 */
export const PhotoScene: React.FC<{
  image?: string;
  stamp: string;
  stampDate: string;
  caption: string;
}> = ({ image, stamp, stampDate, caption }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <Background>
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: 90,
          padding: "90px 130px",
        }}
      >
        {/* Photo plate */}
        <Reveal delay={6} distance={60}>
          <div
            style={{
              position: "relative",
              width: 900,
              height: 560,
              background: "#0d1016",
              border: "8px solid #20242c",
              boxShadow: "0 18px 40px rgba(0,0,0,0.6)",
              overflow: "hidden",
            }}
          >
            {image ? (
              <Img
                src={staticFile(image)}
                style={{ width: "100%", height: "100%", objectFit: "cover", filter: "grayscale(0.9) contrast(1.08)" }}
              />
            ) : (
              <SiteSilhouette />
            )}
            <Tape width={120} height={36} rotate={-40} style={{ top: -12, right: 70 }} />
            <Tape width={120} height={36} rotate={45} style={{ top: -14, left: 90 }} />
          </div>
        </Reveal>

        {/* Stamp + caption */}
        <div style={{ display: "flex", flexDirection: "column", gap: 46, maxWidth: 520 }}>
          <div style={{ transform: `scale(${popIn(frame, 26, fps)})`, transformOrigin: "left center" }}>
            <Stamp text={stamp} sub={stampDate} width={340} />
          </div>
          <Reveal delay={34} distance={40}>
            <div
              style={{
                fontFamily: FONTS.serif,
                fontStyle: "italic",
                fontSize: 38,
                color: COLORS.white,
                lineHeight: 1.4,
                borderLeft: `4px solid ${COLORS.red}`,
                paddingLeft: 26,
              }}
            >
              {caption}
            </div>
          </Reveal>
        </div>
      </div>
    </Background>
  );
};
