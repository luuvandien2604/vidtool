import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Player, type PlayerRef } from "@remotion/player";
import { DocumentaryVideo } from "@core/Root";
import { totalFrames, type SceneType, SCENE_TYPES } from "@core/schema/project";
import { useProject } from "./useProject";
import { Timeline } from "./Timeline";
import { Inspector } from "./Inspector";
import { SCENE_TYPE_LABELS } from "./sceneDefaults";

export const App: React.FC = () => {
  const {
    project,
    file,
    error,
    saveState,
    load,
    save,
    updateScene,
    updateSceneProps,
    addScene,
    removeScene,
    duplicateScene,
    moveScene,
    setSceneDuration,
  } = useProject();

  const [currentFrame, setCurrentFrame] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const playerRef = useRef<PlayerRef>(null);
  const [filePath, setFilePath] = useState("");

  useEffect(() => {
    void load(file);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const selected = useMemo(
    () => project?.scenes.find((s) => s.id === selectedId) ?? null,
    [project, selectedId],
  );

  /* ---------------- keyboard shortcuts ---------------- */

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (e.code === "Space") {
        e.preventDefault();
        const p = playerRef.current;
        if (!p) return;
        if (p.isPlaying()) p.pause();
        else p.play();
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        const p = playerRef.current;
        if (!p || !project) return;
        const f = Math.max(0, currentFrame - Math.round(project.fps * 0.25));
        setCurrentFrame(f);
        p.seekTo(f);
      } else if (e.key === "ArrowRight") {
        e.preventDefault();
        const p = playerRef.current;
        if (!p || !project) return;
        const f = Math.min(totalFrames(project) - 1, currentFrame + Math.round(project.fps * 0.25));
        setCurrentFrame(f);
        p.seekTo(f);
      } else if (e.key === "Delete" || e.key === "Backspace") {
        if (selectedId) removeScene(selectedId);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [currentFrame, selectedId, removeScene, project]);

  const seek = useCallback((frame: number) => {
    setCurrentFrame(frame);
    playerRef.current?.seekTo(frame);
  }, []);

  // Track the playhead from the Player's frameupdate events.
  useEffect(() => {
    const p = playerRef.current;
    if (!p) return;
    const onFrame = (e: { detail: { frame: number } }) => {
      setCurrentFrame(e.detail.frame);
    };
    p.addEventListener("frameupdate", onFrame);
    return () => p.removeEventListener("frameupdate", onFrame);
  }, [project]);

  /* ---------------- render ---------------- */

  if (error) {
    return (
      <div className="app">
        <div className="empty-state">
          <div>⚠️ {error}</div>
          <div>
            <input
              type="text"
              placeholder="examples/chernobyl.project.json"
              value={filePath}
              onChange={(e) => setFilePath(e.target.value)}
              style={{ width: 320, padding: "8px 10px", background: "#121418", color: "#e6e6e6", border: "1px solid #33373e", borderRadius: 4 }}
            />
            <button className="icon-btn primary" style={{ marginLeft: 8 }} onClick={() => void load(filePath)}>
              Load
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="app">
        <div className="empty-state">Loading project…</div>
      </div>
    );
  }

  const duration = totalFrames(project);

  return (
    <div className="app">
      {/* Top bar */}
      <div className="topbar">
        <strong style={{ fontSize: 13 }}>📼 Documentary Editor</strong>
        <span style={{ color: "#7d848d", fontSize: 12 }}>
          {file} · {project.scenes.length} scenes · {(duration / project.fps).toFixed(1)}s
        </span>
        <div className="spacer" />
        <span style={{ fontSize: 11, color: "#7d848d" }}>Space=play · ←/→=seek · Del=remove</span>
        <span className={`save-dot ${saveState}`} title={`Save: ${saveState}`} />
        <button className="icon-btn" onClick={() => void save()}>
          Save
        </button>
        <AddSceneMenu onAdd={(t) => addScene(t, selectedId ?? undefined)} />
      </div>

      {/* Main: player + inspector */}
      <div className="main">
        <div className="player-pane">
          <div className="player-wrap">
            <Player
              ref={playerRef}
              component={DocumentaryVideo}
              inputProps={{ project }}
              durationInFrames={duration}
              fps={project.fps}
              compositionWidth={project.width}
              compositionHeight={project.height}
              controls={false}
              loop={false}
              acknowledgeRemotionLicense
              style={{ width: "100%", height: "100%" }}
            />
          </div>
        </div>
        <Inspector
          scene={selected}
          fps={project.fps}
          updateScene={updateScene}
          updateSceneProps={updateSceneProps}
        />
      </div>

      {/* Timeline */}
      <Timeline
        project={project}
        currentFrame={currentFrame}
        selectedId={selectedId}
        onSeek={seek}
        onSelect={(id) => {
          setSelectedId(id);
          const scene = project.scenes.find((s) => s.id === id);
          if (scene) seek(scene.startFrame);
        }}
        moveScene={moveScene}
        setSceneDuration={setSceneDuration}
        removeScene={removeScene}
        duplicateScene={duplicateScene}
      />
    </div>
  );
};

function AddSceneMenu({ onAdd }: { onAdd: (t: SceneType) => void }) {
  return (
    <select
      defaultValue=""
      onChange={(e) => {
        const v = e.target.value;
        if (v) {
          onAdd(v as SceneType);
          e.target.value = "";
        }
      }}
      style={{ background: "#262a31", color: "#e6e6e6", border: "1px solid #33373e", borderRadius: 4, padding: "5px 8px" }}
    >
      <option value="" disabled>
        + Add scene…
      </option>
      {SCENE_TYPES.map((t) => (
        <option key={t} value={t}>
          {SCENE_TYPE_LABELS[t]}
        </option>
      ))}
    </select>
  );
}
