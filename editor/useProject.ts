import { useCallback, useEffect, useRef, useState } from "react";
import {
  ProjectSchema,
  normalizeTimeline,
  type Project,
  type Scene,
} from "@core/schema/project";
import { createScene } from "./sceneDefaults";

/** Where the project lives on disk (relative to lab root). */
function fileFromUrl(): string {
  const p = new URLSearchParams(window.location.search);
  return p.get("file") ?? "examples/chernobyl.project.json";
}

export function useProject() {
  const [project, setProject] = useState<Project | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [file, setFile] = useState(fileFromUrl());
  const projectRef = useRef<Project | null>(null);
  projectRef.current = project;

  const load = useCallback(async (targetFile: string) => {
    try {
      const res = await fetch(`/api/load?file=${encodeURIComponent(targetFile)}`);
      const json = (await res.json()) as { content?: string; error?: string };
      if (!res.ok || !json.content) throw new Error(json.error ?? "Load failed");
      const parsed = ProjectSchema.parse(JSON.parse(json.content));
      setProject(parsed);
      setFile(targetFile);
      setError(null);
      // Update URL so refresh keeps the same file.
      const url = new URL(window.location.href);
      url.searchParams.set("file", targetFile);
      window.history.replaceState(null, "", url);
    } catch (err) {
      setError((err as Error).message);
    }
  }, []);

  const save = useCallback(async () => {
    const p = projectRef.current;
    if (!p) return;
    setSaveState("saving");
    try {
      const res = await fetch(`/api/save?file=${encodeURIComponent(file)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(p, null, 2),
      });
      if (!res.ok) throw new Error(`Save failed (${res.status})`);
      setSaveState("saved");
      setTimeout(() => setSaveState("idle"), 1500);
    } catch (err) {
      setSaveState("error");
      console.error(err);
    }
  }, [file]);

  // Debounced auto-save on every change.
  const dirtyRef = useRef(false);
  useEffect(() => {
    if (!project) return;
    dirtyRef.current = true;
    const t = setTimeout(() => {
      if (dirtyRef.current) {
        dirtyRef.current = false;
        void save();
      }
    }, 800);
    return () => clearTimeout(t);
  }, [project, save]);

  // --- Mutations (all keep the timeline sequential) ---

  const updateScene = useCallback((sceneId: string, patch: Partial<Scene>) => {
    setProject((prev) => {
      if (!prev) return prev;
      const scenes = prev.scenes.map((s) =>
        s.id === sceneId ? ({ ...s, ...patch } as Scene) : s,
      );
      return syncVoiceover(normalizeTimeline({ ...prev, scenes }));
    });
  }, []);

  const updateSceneProps = useCallback((sceneId: string, props: Scene["props"]) => {
    setProject((prev) => {
      if (!prev) return prev;
      const scenes = prev.scenes.map((s) =>
        s.id === sceneId ? ({ ...s, props } as Scene) : s,
      );
      return { ...prev, scenes } as Project;
    });
  }, []);

  const addScene = useCallback((type: Scene["type"], afterId?: string) => {
    setProject((prev) => {
      if (!prev) return prev;
      const insertAt = afterId
        ? prev.scenes.findIndex((s) => s.id === afterId) + 1
        : prev.scenes.length;
      const startFrame = insertAt > 0
        ? prev.scenes[insertAt - 1].startFrame + prev.scenes[insertAt - 1].durationInFrames
        : 0;
      const scene = createScene(type, prev.fps, startFrame);
      const scenes = [...prev.scenes];
      scenes.splice(insertAt, 0, scene);
      return syncVoiceover(normalizeTimeline({ ...prev, scenes }));
    });
  }, []);

  const removeScene = useCallback((sceneId: string) => {
    setProject((prev) => {
      if (!prev) return prev;
      const scenes = prev.scenes.filter((s) => s.id !== sceneId);
      const voiceover = prev.audio.voiceover.filter((c) => c.sceneId !== sceneId);
      return syncVoiceover({
        ...normalizeTimeline({ ...prev, scenes }),
        audio: { ...prev.audio, voiceover },
      });
    });
  }, []);

  const duplicateScene = useCallback((sceneId: string) => {
    setProject((prev) => {
      if (!prev) return prev;
      const idx = prev.scenes.findIndex((s) => s.id === sceneId);
      if (idx < 0) return prev;
      const src = prev.scenes[idx];
      const copy: Scene = {
        ...structuredClone(src),
        id: `${src.type}-${Math.random().toString(36).slice(2, 7)}`,
        audio: null,
      };
      const scenes = [...prev.scenes];
      scenes.splice(idx + 1, 0, copy);
      return syncVoiceover(normalizeTimeline({ ...prev, scenes }));
    });
  }, []);

  const moveScene = useCallback((sceneId: string, toIndex: number) => {
    setProject((prev) => {
      if (!prev) return prev;
      const from = prev.scenes.findIndex((s) => s.id === sceneId);
      if (from < 0 || toIndex === from) return prev;
      const scenes = [...prev.scenes];
      const [moved] = scenes.splice(from, 1);
      const clamped = Math.max(0, Math.min(toIndex, scenes.length));
      scenes.splice(clamped, 0, moved);
      return syncVoiceover(normalizeTimeline({ ...prev, scenes }));
    });
  }, []);

  const setSceneDuration = useCallback((sceneId: string, durationInFrames: number) => {
    setProject((prev) => {
      if (!prev) return prev;
      const scenes = prev.scenes.map((s) =>
        s.id === sceneId
          ? { ...s, durationInFrames: Math.max(15, Math.round(durationInFrames)) }
          : s,
      );
      return syncVoiceover(normalizeTimeline({ ...prev, scenes }));
    });
  }, []);

  return {
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
  };
}

/** Keeps voiceover clip start times aligned with (re-ordered) scenes. */
function syncVoiceover(project: Project): Project {
  const voiceover = project.audio.voiceover.map((clip) => {
    const scene = project.scenes.find((s) => s.id === clip.sceneId);
    return scene ? { ...clip, startFrame: scene.startFrame } : clip;
  });
  return { ...project, audio: { ...project.audio, voiceover } };
}
