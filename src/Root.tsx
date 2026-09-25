import React from "react";
import {
  AbsoluteFill,
  Audio,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { SceneRouter } from "./scenes/SceneRouter";
import { CaptionBar } from "./theme/Overlays";
import { totalFrames, type Project, type Scene } from "./schema/project";

const TRANSITION_FRAMES = 12;

/**
 * Wraps a scene with its entrance transition + caption bar.
 * Shared by CLI rendering and the editor preview.
 */
const SceneWithTransition: React.FC<{ scene: Scene; project: Project }> = ({
  scene,
  project,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const tf = Math.min(TRANSITION_FRAMES, scene.durationInFrames - 1);
  const t = interpolate(frame, [0, tf], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  let opacity = 1;
  let translateX = 0;
  let scale = 1;

  switch (scene.transition) {
    case "fade":
      opacity = t;
      break;
    case "slide":
      translateX = (1 - t) * 90;
      opacity = t;
      break;
    case "zoom":
      scale = 0.9 + 0.1 * t;
      opacity = t;
      break;
    case "none":
      break;
  }

  // Voiceover clip for this scene (started at scene start).
  const clip = project.audio.voiceover.find((c) => c.sceneId === scene.id);

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        opacity,
        transform: `translateX(${translateX}px) scale(${scale})`,
      }}
    >
      <SceneRouter scene={scene} />
      {clip ? (
        <Audio src={staticFile(clip.file)} volume={1} />
      ) : null}
      {scene.captions && scene.narration ? (
        <CaptionBar text={scene.narration} />
      ) : null}
    </div>
  );
};

/**
 * The one video composition: plays every scene sequentially.
 */
export const DocumentaryVideo: React.FC<{ project: Project }> = ({
  project,
}) => {
  const duration = totalFrames(project);
  return (
    <AbsoluteFill style={{ background: "#05070c" }}>
      {project.scenes.map((scene) => (
        <Sequence
          key={scene.id}
          from={scene.startFrame}
          durationInFrames={scene.durationInFrames}
          premountFor={Math.min(TRANSITION_FRAMES, scene.durationInFrames)}
        >
          <SceneWithTransition scene={scene} project={project} />
        </Sequence>
      ))}

      {/* Global music bed (optional) */}
      {project.audio.music ? (
        <Sequence from={0} durationInFrames={duration}>
          <Audio src={staticFile(project.audio.music)} volume={0.16} loop />
        </Sequence>
      ) : null}
    </AbsoluteFill>
  );
};

export const DOCUMENTARY_COMPOSITION_ID = "DocumentaryVideo";

export { SceneWithTransition };
