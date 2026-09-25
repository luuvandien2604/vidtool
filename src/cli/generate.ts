import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  ProjectSchema,
  normalizeTimeline,
  type Project,
  type Scene,
} from "../schema/project";
import { ContentSchema, fallbackContent, llmConfigured, llmContent } from "./content";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "../..");

/* ------------------------------------------------------------------ */
/* Args                                                                */
/* ------------------------------------------------------------------ */

interface CliArgs {
  topic: string;
  lang: "vi" | "en";
  out: string;
  llm: boolean;
  fps: number;
  width: number;
  height: number;
}

function parseArgs(argv: string[]): CliArgs {
  const args: CliArgs = {
    topic: "",
    lang: "vi",
    out: "",
    llm: true,
    fps: 30,
    width: 1920,
    height: 1080,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    const next = () => argv[++i];
    switch (a) {
      case "--topic":
        args.topic = next() ?? "";
        break;
      case "--lang":
        args.lang = next() === "en" ? "en" : "vi";
        break;
      case "--out":
        args.out = next() ?? "";
        break;
      case "--no-llm":
        args.llm = false;
        break;
      case "--fps":
        args.fps = Number(next()) || 30;
        break;
      case "--width":
        args.width = Number(next()) || 1920;
        break;
      case "--height":
        args.height = Number(next()) || 1080;
        break;
      case "--help":
      case "-h":
        console.log(
          [
            "Usage: npm run generate -- --topic \"<topic>\" [options]",
            "",
            "Options:",
            "  --topic <text>    Topic of the video (required)",
            "  --lang vi|en      Content language (default: vi)",
            "  --out <path>      Output project.json path (default: examples/<slug>.project.json)",
            "  --no-llm          Skip LLM autofill, use offline fallback content",
            "  --fps <n>         Frames per second (default: 30)",
            "  --width <n>       Video width (default: 1920)",
            "  --height <n>      Video height (default: 1080)",
          ].join("\n"),
        );
        process.exit(0);
    }
  }
  if (!args.topic) {
    console.error("Error: --topic is required. Run with --help for usage.");
    process.exit(1);
  }
  return args;
}

/* ------------------------------------------------------------------ */
/* Timeline assembly                                                   */
/* ------------------------------------------------------------------ */

/** Rough speech-duration estimate from narration length (seconds). */
function estimateNarrationSeconds(text: string | undefined, lang: string): number {
  if (!text) return 5;
  // Vietnamese/English average ~17-20 chars per spoken second.
  const cps = lang === "vi" ? 16 : 15;
  return Math.min(20, Math.max(5, text.length / cps + 1.2));
}

function buildScene(
  id: string,
  type: Scene["type"],
  props: Scene["props"],
  narration: string,
  transition: Scene["transition"],
  lang: string,
  fps: number,
  projectId: string,
): Scene {
  const seconds = estimateNarrationSeconds(narration, lang);
  const base = {
    id,
    type,
    startFrame: 0, // normalized later
    durationInFrames: Math.round(seconds * fps),
    transition,
    narration,
    // Namespaced under projectId so different projects never share audio files.
    audio: `audio/${projectId}/scene-${id}.mp3`,
    captions: true,
  } as Scene;
  return { ...base, props } as Scene;
}

function contentToProject(content: unknown, topic: string, args: CliArgs): Project {
  const c = ContentSchema.parse(content);
  const slug = topic
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "")
    .slice(0, 40) || "video";

  // Curry buildScene with the resolved project slug so all audio paths are
  // namespaced: public/audio/<projectId>/scene-<id>.mp3
  const mk = (
    id: string,
    type: Scene["type"],
    props: Scene["props"],
    narration: string,
    transition: Scene["transition"],
  ) => buildScene(id, type, props, narration, transition, args.lang, args.fps, slug);

  const scenes: Scene[] = [
    mk("intro", "intro", {
      kicker: c.kicker,
      title: c.title,
      subtitle: c.subtitle,
      date: c.date,
      time: c.time,
      hazard: true,
    }, c.introNarration, "fade"),
    mk("context", "bullets", {
      heading: c.context.heading,
      items: c.context.items,
      numbered: true,
    }, c.contextNarration, "slide"),
    mk("diagram", "diagram", {
      heading: c.diagram.heading,
      kind: "reactor" as const,
      caption: c.diagram.caption,
      nodes: c.diagram.nodes.map((n, i) => ({
        label: n.label,
        description: n.description,
        x: 82 - i * 3,
        y: 20 + i * 22,
      })),
    }, c.diagramNarration, "fade"),
    mk("comparison", "comparison", {
      headingA: c.comparison.headingA,
      itemsA: c.comparison.itemsA,
      headingB: c.comparison.headingB,
      itemsB: c.comparison.itemsB,
      showSchematic: true,
    }, c.comparisonNarration, "fade"),
    mk("chart", "chart", {
      heading: c.chart.heading,
      xLabels: c.chart.xLabels,
      yTicks: c.chart.yTicks,
      data: c.chart.data,
      annotation: c.chart.annotation,
      eventLabel: c.chart.eventLabel,
    }, c.chartNarration, "fade"),
    mk("photo", "photo", {
      stamp: c.photo.stamp,
      stampDate: c.photo.stampDate,
      caption: c.photo.caption,
    }, c.photoNarration, "slide"),
    mk("summary", "summary", {
      heading: c.summary.heading,
      points: c.summary.points,
    }, c.summaryNarration, "fade"),
  ];

  const project: Project = {
    id: slug,
    topic,
    title: `${c.title.toUpperCase()} — ${c.kicker}`,
    lang: args.lang,
    fps: args.fps,
    width: args.width,
    height: args.height,
    scenes,
    audio: { voiceover: [], music: null },
  };
  return ProjectSchema.parse(normalizeTimeline(project));
}

/* ------------------------------------------------------------------ */
/* Main                                                                */
/* ------------------------------------------------------------------ */

async function main() {
  const args = parseArgs(process.argv.slice(2));

  let content: unknown;
  if (args.llm && llmConfigured()) {
    console.log(`🤖 Generating content via LLM (topic: "${args.topic}")...`);
    try {
      content = await llmContent(args.topic, args.lang);
      console.log("   LLM content ready.");
    } catch (err) {
      console.warn(`   LLM failed (${(err as Error).message}) — falling back to template content.`);
      content = fallbackContent(args.topic, args.lang);
    }
  } else {
    console.log(`📄 Using offline template content (topic: "${args.topic}")...`);
    content = fallbackContent(args.topic, args.lang);
  }

  const project = contentToProject(content, args.topic, args);
  const outPath = args.out
    ? path.resolve(ROOT, args.out)
    : path.join(ROOT, "examples", `${project.id}.project.json`);

  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  fs.writeFileSync(outPath, JSON.stringify(project, null, 2) + "\n", "utf-8");

  const totalSec = project.scenes.reduce((s, sc) => s + sc.durationInFrames, 0) / args.fps;
  console.log("");
  console.log(`✅ project.json written: ${outPath}`);
  console.log(`   Scenes: ${project.scenes.length} | Total: ${totalSec.toFixed(1)}s @ ${args.fps}fps`);
  console.log("");
  console.log("Next steps:");
  console.log(`  npm run tts -- --input ${path.relative(ROOT, outPath)}   # voiceover (optional)`);
  console.log(`  npm run render -- --input ${path.relative(ROOT, outPath)}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
