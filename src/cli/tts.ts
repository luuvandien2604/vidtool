import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { EdgeTTS } from "node-edge-tts";
import { ProjectSchema, type Project } from "../schema/project";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "../..");

/* ------------------------------------------------------------------ */
/* Args                                                                */
/* ------------------------------------------------------------------ */

function parseArgs(argv: string[]): { input: string; voice?: string } {
  let input = "";
  let voice: string | undefined;
  for (let i = 0; i < argv.length; i++) {
    switch (argv[i]) {
      case "--input":
        input = argv[++i] ?? "";
        break;
      case "--voice":
        voice = argv[++i];
        break;
      case "--help":
      case "-h":
        console.log(
          [
            "Usage: npm run tts -- --input <project.json> [--voice <voice>]",
            "",
            "Generates one MP3 voiceover per scene into public/audio/",
            "and fills project.audio.voiceover + scene.audio paths.",
            "",
            "Default voices:",
            "  vi -> vi-VN-HoaiMyNeural",
            "  en -> en-US-ChristopherNeural",
          ].join("\n"),
        );
        process.exit(0);
    }
  }
  if (!input) {
    console.error("Error: --input is required.");
    process.exit(1);
  }
  return { input, voice };
}

/* ------------------------------------------------------------------ */
/* Main                                                                */
/* ------------------------------------------------------------------ */

async function main() {
  const { input, voice } = parseArgs(process.argv.slice(2));
  const inPath = path.resolve(ROOT, input);
  const project: Project = ProjectSchema.parse(
    JSON.parse(fs.readFileSync(inPath, "utf-8")),
  );

  const defaultVoice =
    project.lang === "en" ? "en-US-ChristopherNeural" : "vi-VN-HoaiMyNeural";
  const ttsVoice = voice ?? defaultVoice;
  const audioDir = path.join(ROOT, "public", "audio");
  fs.mkdirSync(audioDir, { recursive: true });

  console.log(`🎙️  TTS voice: ${ttsVoice}`);
  const tts = new EdgeTTS({
    voice: ttsVoice,
    lang: project.lang === "en" ? "en-US" : "vi-VN",
    outputFormat: "audio-24khz-48kbitrate-mono-mp3",
  });

  const voiceover: Project["audio"]["voiceover"] = [];
  let failed = 0;

  for (const scene of project.scenes) {
    if (!scene.narration) continue;
    const file = scene.audio ?? `audio/scene-${scene.id}.mp3`;
    const outPath = path.join(ROOT, "public", file);
    const url = file.replace(/\\/g, "/");

    if (fs.existsSync(outPath)) {
      console.log(`  (exists) ${url}`);
      voiceover.push({
        sceneId: scene.id,
        file: url,
        startFrame: scene.startFrame,
        durationInFrames: scene.durationInFrames,
      });
      continue;
    }

    try {
      console.log(`  ⏳ synthesizing: ${scene.narration.slice(0, 48)}...`);
      await tts.ttsPromise(scene.narration, outPath);
      voiceover.push({
        sceneId: scene.id,
        file: url,
        startFrame: scene.startFrame,
        durationInFrames: scene.durationInFrames,
      });
      console.log(`  ✅ ${url}`);
    } catch (err) {
      failed++;
      console.warn(`  ⚠️  failed (${(err as Error).message}) — scene will be silent`);
    }
  }

  project.audio = { ...project.audio, voiceover };
  fs.writeFileSync(inPath, JSON.stringify(project, null, 2) + "\n", "utf-8");

  console.log("");
  if (failed > 0) {
    console.warn(`⚠️  ${failed} clip(s) failed (check network). Video still renders, silently.`);
  } else {
    console.log(`✅ ${voiceover.length} voiceover clips ready + project.json updated.`);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
