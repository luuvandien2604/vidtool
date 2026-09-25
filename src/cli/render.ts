import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import { ProjectSchema, totalFrames, type Project } from "../schema/project";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "../..");

/* ------------------------------------------------------------------ */
/* Args                                                                */
/* ------------------------------------------------------------------ */

function parseArgs(argv: string[]): {
  input: string;
  output?: string;
  concurrency?: number;
  quality?: number;
} {
  const args: Record<string, string> = {};
  for (let i = 0; i < argv.length; i++) {
    switch (argv[i]) {
      case "--input":
        args.input = argv[++i] ?? "";
        break;
      case "--output":
        args.output = argv[++i];
        break;
      case "--concurrency":
        args.concurrency = argv[++i];
        break;
      case "--quality":
        args.quality = argv[++i];
        break;
      case "--help":
      case "-h":
        console.log(
          [
            "Usage: npm run render -- --input <project.json> [options]",
            "",
            "Options:",
            "  --input <path>      project.json to render (required)",
            "  --output <path>     Output MP4 path (default: out/<projectId>.mp4)",
            "  --concurrency <n>   ffmpeg threads (default: half of CPUs)",
            "  --quality <0-100>   CRF-based quality, higher = better (default: 70)",
          ].join("\n"),
        );
        process.exit(0);
    }
  }
  if (!args.input) {
    console.error("Error: --input is required. Run with --help for usage.");
    process.exit(1);
  }
  return {
    input: args.input,
    output: args.output,
    concurrency: args.concurrency ? Number(args.concurrency) : undefined,
    quality: args.quality ? Number(args.quality) : undefined,
  };
}

/* ------------------------------------------------------------------ */
/* Main                                                                */
/* ------------------------------------------------------------------ */

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const inPath = path.resolve(ROOT, args.input);
  const project: Project = ProjectSchema.parse(
    JSON.parse(fs.readFileSync(inPath, "utf-8")),
  );

  const duration = totalFrames(project);
  const outPath = args.output
    ? path.resolve(ROOT, args.output)
    : path.join(ROOT, "out", `${project.id}.mp4`);
  fs.mkdirSync(path.dirname(outPath), { recursive: true });

  const missingAudio = project.audio.voiceover.filter((c) => {
    const p = path.join(ROOT, "public", c.file);
    return !fs.existsSync(p);
  });
  if (missingAudio.length > 0) {
    console.warn(
      `⚠️  ${missingAudio.length} voiceover file(s) missing — run "npm run tts -- --input ${args.input}" first (video still renders without audio).`,
    );
  }

  console.log(`📦 Bundling Remotion project...`);
  const serveUrl = await bundle({
    entryPoint: path.join(ROOT, "src", "index.tsx"),
    webpackOverride: (config) => config,
  });

  console.log(`🎬 Rendering "${project.id}" (${duration} frames @ ${project.fps}fps → ${(duration / project.fps).toFixed(1)}s)...`);

  const composition = await selectComposition({
    serveUrl,
    id: "DocumentaryVideo",
    inputProps: { project },
  });

  const start = Date.now();
  await renderMedia({
    composition,
    serveUrl,
    codec: "h264",
    outputLocation: outPath,
    inputProps: { project },
    concurrency: args.concurrency,
    crf: args.quality,
    onProgress: ({ progress, renderedFrames, encodedFrames }) => {
      if (renderedFrames % 30 === 0 || progress === 1) {
        process.stdout.write(
          `\r   ${(progress * 100).toFixed(0)}%  (${renderedFrames}/${duration} frames rendered, ${encodedFrames} encoded)`,
        );
      }
    },
  });

  const elapsed = ((Date.now() - start) / 1000).toFixed(1);
  console.log(`\n✅ Done in ${elapsed}s → ${outPath}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
