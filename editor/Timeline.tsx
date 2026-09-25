import React, { useRef, useState } from "react";
import type { Project, Scene } from "@core/schema/project";
import { SCENE_TYPE_COLORS } from "./sceneDefaults";

const PX_PER_SEC = 44;

type DragState =
  | { kind: "move"; sceneId: string; startX: number; dx: number; targetIndex: number }
  | { kind: "resize"; sceneId: string; startX: number; startDurFrames: number }
  | null;

interface TimelineProps {
  project: Project;
  currentFrame: number;
  selectedId: string | null;
  onSeek: (frame: number) => void;
  onSelect: (id: string) => void;
  moveScene: (id: string, toIndex: number) => void;
  setSceneDuration: (id: string, frames: number) => void;
  removeScene: (id: string) => void;
  duplicateScene: (id: string) => void;
}

export const Timeline: React.FC<TimelineProps> = ({
  project,
  currentFrame,
  selectedId,
  onSeek,
  onSelect,
  moveScene,
  setSceneDuration,
  removeScene,
  duplicateScene,
}) => {
  const { fps, scenes } = project;
  const totalSec = scenes.reduce((a, s) => a + s.durationInFrames, 0) / fps;
  const width = Math.max(1200, totalSec * PX_PER_SEC + 80);
  const [drag, setDrag] = useState<DragState>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const rulerRef = useRef<HTMLDivElement>(null);

  const frameToX = (f: number) => (f / fps) * PX_PER_SEC;
  const xToFrame = (x: number) => (x / PX_PER_SEC) * fps;

  const sceneWidth = (s: Scene) => (s.durationInFrames / fps) * PX_PER_SEC;

  /* ---------------- pointer interactions ---------------- */

  const onRulerClick = (e: React.MouseEvent) => {
    const rect = rulerRef.current!.getBoundingClientRect();
    onSeek(Math.max(0, Math.round(xToFrame(e.clientX - rect.left + (scrollRef.current?.scrollLeft ?? 0)))));
  };

  const startMove = (e: React.PointerEvent, scene: Scene) => {
    e.preventDefault();
    const idx = scenes.findIndex((s) => s.id === scene.id);
    setDrag({ kind: "move", sceneId: scene.id, startX: e.clientX, dx: 0, targetIndex: idx });
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  };

  const startResize = (e: React.PointerEvent, scene: Scene) => {
    e.stopPropagation();
    e.preventDefault();
    setDrag({ kind: "resize", sceneId: scene.id, startX: e.clientX, startDurFrames: scene.durationInFrames });
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  };

  const onPointerMove = (e: React.PointerEvent) => {
    if (!drag) return;
    const dx = e.clientX - drag.startX;

    if (drag.kind === "move") {
      const dragged = scenes.find((s) => s.id === drag.sceneId);
      if (!dragged) return;
      const draggedLeft = frameToX(dragged.startFrame) + dx;
      const draggedW = sceneWidth(dragged);
      const center = draggedLeft + draggedW / 2;
      // compute target index among other scenes
      const others = scenes.filter((s) => s.id !== drag.sceneId);
      let idx = 0;
      for (const o of others) {
        const oCenter = frameToX(o.startFrame) + sceneWidth(o) / 2;
        if (center > oCenter) idx++;
      }
      setDrag({ ...drag, dx, targetIndex: idx });
    } else {
      const newDur = Math.max(0.5, (drag.startDurFrames / fps) + dx / PX_PER_SEC);
      setSceneDuration(drag.sceneId, Math.round(newDur * fps));
    }
  };

  const onPointerUp = () => {
    if (drag?.kind === "move") {
      moveScene(drag.sceneId, drag.targetIndex);
    }
    setDrag(null);
  };

  /* ---------------- render ---------------- */

  const playheadX = frameToX(currentFrame);
  const dropIndicatorX =
    drag?.kind === "move" ? computeIndicatorX(scenes, drag.sceneId, drag.targetIndex, frameToX, sceneWidth) : null;

  const ticks = Math.ceil(totalSec);
  const tickStep = totalSec > 60 ? 10 : totalSec > 20 ? 5 : 2;

  return (
    <div className="timeline-pane">
      <div className="timeline-scroll" ref={scrollRef}>
        <div className="timeline-inner" style={{ width }}>
          {/* Ruler */}
          <div className="ruler" ref={rulerRef} onPointerDown={onRulerClick}>
            {Array.from({ length: Math.floor(ticks / tickStep) + 1 }).map((_, i) => {
              const sec = i * tickStep;
              return (
                <React.Fragment key={sec}>
                  <div className="tick" style={{ left: sec * PX_PER_SEC }} />
                  <div className="tick-label" style={{ left: sec * PX_PER_SEC }}>
                    {fmtTime(sec)}
                  </div>
                </React.Fragment>
              );
            })}
          </div>

          {/* Scene track */}
          <div className="scene-track" onPointerMove={onPointerMove} onPointerUp={onPointerUp}>
            <span className="track-label">SCENES</span>
            {dropIndicatorX !== null && <div className="drop-indicator" style={{ left: dropIndicatorX }} />}
            {scenes.map((scene) => {
              const left = frameToX(scene.startFrame);
              const w = sceneWidth(scene);
              const color = SCENE_TYPE_COLORS[scene.type];
              const isDragging = drag?.kind === "move" && drag.sceneId === scene.id;
              return (
                <div
                  key={scene.id}
                  className={`scene-block ${selectedId === scene.id ? "selected" : ""}`}
                  style={{
                    left,
                    width: w,
                    background: `${color}33`,
                    borderColor: `${color}88`,
                    opacity: isDragging ? 0.65 : 1,
                    transform:
                      drag?.kind === "move" && drag.sceneId === scene.id
                        ? `translateX(${drag.dx}px)`
                        : undefined,
                    zIndex: isDragging ? 4 : 1,
                  }}
                  onPointerDown={(e) => {
                    onSelect(scene.id);
                    startMove(e, scene);
                  }}
                >
                  <span className="name" style={{ color }}>
                    {scene.type.toUpperCase()}
                  </span>
                  <span className="dur">{(scene.durationInFrames / fps).toFixed(1)}s</span>
                  <span className="block-actions">
                    <button
                      className="icon-btn"
                      title="Duplicate"
                      onPointerDown={(e) => e.stopPropagation()}
                      onClick={(e) => {
                        e.stopPropagation();
                        duplicateScene(scene.id);
                      }}
                    >
                      ⧉
                    </button>
                    <button
                      className="icon-btn danger"
                      title="Delete"
                      onPointerDown={(e) => e.stopPropagation()}
                      onClick={(e) => {
                        e.stopPropagation();
                        removeScene(scene.id);
                      }}
                    >
                      ✕
                    </button>
                  </span>
                  <div
                    className="resize-handle"
                    onPointerDown={(e) => startResize(e, scene)}
                    onPointerMove={(e) => e.stopPropagation()}
                  />
                </div>
              );
            })}
          </div>

          {/* Voiceover track (display only in v1) */}
          <div className="voice-track">
            <span className="track-label">VOICEOVER</span>
            {project.audio.voiceover.map((clip) => (
              <div
                key={clip.sceneId}
                className="voice-clip"
                style={{
                  left: frameToX(clip.startFrame),
                  width: Math.max(24, (clip.durationInFrames / fps) * PX_PER_SEC - 4),
                }}
                title={clip.file}
              >
                {clip.file}
              </div>
            ))}
          </div>

          {/* Playhead */}
          <div className="playhead" style={{ left: playheadX }} />
        </div>
      </div>
    </div>
  );
};

/* ---------------- helpers ---------------- */

function fmtTime(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

function computeIndicatorX(
  scenes: Scene[],
  dragId: string,
  targetIndex: number,
  frameToX: (f: number) => number,
  sceneWidth: (s: Scene) => number,
): number | null {
  const others = scenes.filter((s) => s.id !== dragId);
  if (targetIndex <= 0) {
    return others.length ? frameToX(others[0].startFrame) - 2 : 0;
  }
  if (targetIndex >= others.length) {
    const last = others[others.length - 1];
    return frameToX(last.startFrame) + sceneWidth(last) + 2;
  }
  const before = others[targetIndex - 1];
  return frameToX(before.startFrame) + sceneWidth(before) + 2;
}
