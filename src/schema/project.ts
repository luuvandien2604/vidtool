import { z } from "zod";

/**
 * project.json — single source of truth for a video.
 * Read/written by both the CLI (generate/render) and the timeline editor.
 */

export const TRANSITIONS = ["none", "fade", "slide", "zoom"] as const;
export const SCENE_TYPES = [
  "intro",
  "bullets",
  "diagram",
  "comparison",
  "chart",
  "photo",
  "summary",
] as const;

export const TransitionSchema = z.enum(TRANSITIONS);

const BaseSceneSchema = z.object({
  id: z.string().min(1),
  type: z.enum(SCENE_TYPES),
  startFrame: z.number().int().min(0),
  durationInFrames: z.number().int().min(1),
  transition: TransitionSchema.default("fade"),
  /** Narration text: used for TTS, captions and duration estimation. */
  narration: z.string().optional(),
  /** Audio file path relative to `public/`. */
  audio: z.string().nullable().optional(),
  captions: z.boolean().default(true),
});

const IntroScenePropsSchema = z.object({
  kicker: z.string(),
  title: z.string(),
  subtitle: z.string(),
  date: z.string().optional(),
  time: z.string().optional(),
  hazard: z.boolean().default(true),
});

const BulletsScenePropsSchema = z.object({
  heading: z.string(),
  items: z.array(z.string()).min(1),
  numbered: z.boolean().default(true),
});

const DiagramScenePropsSchema = z.object({
  heading: z.string(),
  kind: z.enum(["reactor", "flow", "stack"]).default("reactor"),
  caption: z.string().optional(),
  nodes: z
    .array(
      z.object({
        label: z.string(),
        description: z.string().optional(),
        /** Anchor in % of the diagram box, 0..100. */
        x: z.number().min(0).max(100),
        y: z.number().min(0).max(100),
      }),
    )
    .default([]),
});

const ComparisonScenePropsSchema = z.object({
  headingA: z.string(),
  itemsA: z.array(z.string()).min(1),
  headingB: z.string(),
  itemsB: z.array(z.string()).min(1),
  showSchematic: z.boolean().default(true),
});

const ChartScenePropsSchema = z.object({
  heading: z.string(),
  xLabels: z.array(z.string()).min(2),
  yTicks: z.array(z.number()).min(2),
  data: z.array(z.number()).min(2),
  annotation: z.string().optional(),
  eventLabel: z.string().optional(),
});

const PhotoScenePropsSchema = z.object({
  image: z.string().optional(),
  stamp: z.string(),
  stampDate: z.string(),
  caption: z.string(),
});

const SummaryScenePropsSchema = z.object({
  heading: z.string(),
  points: z.array(z.string()).min(1),
});

export const SceneSchema = z.discriminatedUnion("type", [
  BaseSceneSchema.extend({ type: z.literal("intro"), props: IntroScenePropsSchema }),
  BaseSceneSchema.extend({ type: z.literal("bullets"), props: BulletsScenePropsSchema }),
  BaseSceneSchema.extend({ type: z.literal("diagram"), props: DiagramScenePropsSchema }),
  BaseSceneSchema.extend({ type: z.literal("comparison"), props: ComparisonScenePropsSchema }),
  BaseSceneSchema.extend({ type: z.literal("chart"), props: ChartScenePropsSchema }),
  BaseSceneSchema.extend({ type: z.literal("photo"), props: PhotoScenePropsSchema }),
  BaseSceneSchema.extend({ type: z.literal("summary"), props: SummaryScenePropsSchema }),
]);

export const AudioClipSchema = z.object({
  sceneId: z.string(),
  file: z.string(),
  startFrame: z.number().int().min(0),
  durationInFrames: z.number().int().min(1),
});

export const ProjectSchema = z.object({
  id: z.string(),
  topic: z.string(),
  title: z.string(),
  lang: z.enum(["vi", "en"]).default("vi"),
  fps: z.number().int().min(1).max(120).default(30),
  width: z.number().int().default(1920),
  height: z.number().int().default(1080),
  scenes: z.array(SceneSchema).min(1),
  audio: z
    .object({
      voiceover: z.array(AudioClipSchema).default([]),
      music: z.string().nullable().default(null),
    })
    .default({ voiceover: [], music: null }),
});

export type Transition = z.infer<typeof TransitionSchema>;
export type SceneType = (typeof SCENE_TYPES)[number];
export type Project = z.infer<typeof ProjectSchema>;
export type Scene = z.infer<typeof SceneSchema>;
export type SceneProps = Scene["props"];
export type AudioClip = z.infer<typeof AudioClipSchema>;

/** Total length of the video in frames. */
export function totalFrames(project: Project): number {
  return project.scenes.reduce(
    (acc, s) => Math.max(acc, s.startFrame + s.durationInFrames),
    0,
  );
}

/** Ensures scenes are sequential (v1: no overlapping tracks). */
export function normalizeTimeline(project: Project): Project {
  let cursor = 0;
  const scenes = project.scenes.map((s) => {
    const next = { ...s, startFrame: cursor };
    cursor += s.durationInFrames;
    return next;
  });
  return { ...project, scenes };
}
