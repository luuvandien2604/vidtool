import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { EdgeTTS } from "node-edge-tts";
import { ProjectSchema, type Project } from "../schema/project";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "../..");

const TTS_TIMEOUT_MS = 20_000;   // per-request WebSocket timeout
const MAX_RETRIES    = 3;         // per clip (initial attempt + 2 retries)
const RETRY_SLEEP_MS = 2_000;     // base delay, multiplied by attempt index

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
            "Generates one MP3 voiceover per scene into public/audio/<projectId>/",
            "and fills project.audio.voiceover + scene.audio paths.",
            "Each project stores audio in its own subdirectory — no cross-project collision.",
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
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

function sleep(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}

/** Returns true if the file exists AND has size > 0 (non-empty). */
function fileValid(p: string): boolean {
  try {
    return fs.statSync(p).size > 0;
  } catch {
    return false;
  }
}

/** Normalise any thrown value to a printable message. */
function errMsg(err: unknown): string {
  if (err instanceof Error) return err.message || err.constructor.name;
  const s = String(err);
  return s === "undefined" || s === "" ? "(no message — likely TTS WebSocket timeout)" : s;
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

  // Per-project audio subdirectory: public/audio/<projectId>/
  const audioDir = path.join(ROOT, "public", "audio", project.id);
  fs.mkdirSync(audioDir, { recursive: true });

  console.log(`🎙️  TTS voice: ${ttsVoice}  (timeout: ${TTS_TIMEOUT_MS / 1000}s, retries: ${MAX_RETRIES})`);
  console.log(`📁 Audio dir: public/audio/${project.id}/`);

  const voiceover: Project["audio"]["voiceover"] = [];
  let failed = 0;

  for (const scene of project.scenes) {
    if (!scene.narration) continue;

    // Derive a namespaced audio path for this scene under this project.
    // scene.audio may already carry the namespaced value from generate, but
    // we always re-derive it here to stay consistent.
    const relFile = `audio/${project.id}/scene-${scene.id}.mp3`;
    const outPath = path.join(ROOT, "public", relFile);

    if (fileValid(outPath)) {
      console.log(`  (exists) ${relFile}`);
      voiceover.push({
        sceneId: scene.id,
        file: relFile,
        startFrame: scene.startFrame,
        durationInFrames: scene.durationInFrames,
      });
      continue;
    }

    // Attempt synthesis with retries.
    let succeeded = false;
    for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
      const prefix = MAX_RETRIES > 1 ? ` [${attempt}/${MAX_RETRIES}]` : "";
      console.log(`  ⏳${prefix} synthesizing: ${scene.narration.slice(0, 52)}...`);
      // Always create a fresh EdgeTTS instance per attempt (resets WebSocket).
      const tts = new EdgeTTS({
        voice: ttsVoice,
        lang: project.lang === "en" ? "en-US" : "vi-VN",
        outputFormat: "audio-24khz-48kbitrate-mono-mp3",
        timeout: TTS_TIMEOUT_MS,
      });
      try {
        await tts.ttsPromise(scene.narration, outPath);
        // Guard: make sure the file is non-empty before declaring success.
        if (!fileValid(outPath)) {
          throw new Error("synthesis produced an empty file");
        }
        voiceover.push({
          sceneId: scene.id,
          file: relFile,
          startFrame: scene.startFrame,
          durationInFrames: scene.durationInFrames,
        });
        console.log(`  ✅ ${relFile}`);
        succeeded = true;
        break;
      } catch (err) {
        // Remove any partial / empty output so the next attempt re-synthesizes.
        try { fs.unlinkSync(outPath); } catch { /* already gone */ }
        const reason = errMsg(err);
        if (attempt < MAX_RETRIES) {
          console.warn(`  ⚠️  attempt ${attempt} failed: ${reason} — retrying in ${RETRY_SLEEP_MS * attempt / 1000}s...`);
          await sleep(RETRY_SLEEP_MS * attempt);
        } else {
          console.error(`  ❌ all ${MAX_RETRIES} attempts failed for scene "${scene.id}": ${reason}`);
          failed++;
        }
      }
    }
    if (!succeeded && !failed) failed++; // safety counter
  }

  project.audio = { ...project.audio, voiceover };
  fs.writeFileSync(inPath, JSON.stringify(project, null, 2) + "\n", "utf-8");

  console.log("");
  if (failed > 0) {
    console.warn(`⚠️  ${failed} scene(s) have no audio after ${MAX_RETRIES} attempts. Check your network and rerun — empty files have been removed so they will be retried.`);
    process.exitCode = 1;
  } else {
    console.log(`✅ ${voiceover.length} voiceover clips ready → public/audio/${project.id}/`);
    console.log(`   project.json updated: ${input}`);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
