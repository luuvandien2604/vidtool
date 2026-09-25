import fs from "node:fs";
import path from "node:path";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

const LAB_ROOT = __dirname;
const PUBLIC_DIR = path.join(LAB_ROOT, "public");

const CONTENT_TYPES: Record<string, string> = {
  ".mp3": "audio/mpeg",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".webp": "image/webp",
  ".svg": "image/svg+xml",
  ".json": "application/json",
};

/**
 * Dev middleware:
 *  - GET  /api/load?file=<rel>   -> read project.json (must live under LAB_ROOT)
 *  - PUT  /api/save?file=<rel>   -> write project.json back (auto-save target)
 *  - GET  /audio/*, /images/*    -> static files from public/ (Remotion staticFile)
 */
function projectApiPlugin(): Plugin {
  return {
    name: "project-api",
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const url = new URL(req.url ?? "/", "http://localhost");
        const sendJson = (code: number, body: unknown) => {
          res.statusCode = code;
          res.setHeader("Content-Type", "application/json");
          res.end(JSON.stringify(body));
        };

        if (url.pathname === "/api/load") {
          const file = url.searchParams.get("file") ?? "";
          const target = path.resolve(LAB_ROOT, file);
          if (!target.startsWith(LAB_ROOT) || !fs.existsSync(target)) {
            sendJson(404, { error: `File not found: ${file}` });
            return;
          }
          const content = fs.readFileSync(target, "utf-8");
          sendJson(200, { file, content });
          return;
        }

        if (url.pathname === "/api/save" && req.method === "PUT") {
          const file = url.searchParams.get("file") ?? "";
          const target = path.resolve(LAB_ROOT, file);
          if (!target.startsWith(LAB_ROOT)) {
            sendJson(400, { error: "Invalid path" });
            return;
          }
          let body = "";
          req.on("data", (chunk) => (body += chunk));
          req.on("end", () => {
            try {
              fs.mkdirSync(path.dirname(target), { recursive: true });
              fs.writeFileSync(target, body, "utf-8");
              sendJson(200, { ok: true });
            } catch (err) {
              sendJson(500, { error: (err as Error).message });
            }
          });
          return;
        }

        // Static public assets (audio/, images/)
        if (
          (url.pathname.startsWith("/audio/") || url.pathname.startsWith("/images/")) &&
          req.method === "GET"
        ) {
          const rel = url.pathname.replace(/^\/+/, "");
          const target = path.join(PUBLIC_DIR, rel);
          if (!target.startsWith(PUBLIC_DIR) || !fs.existsSync(target)) {
            res.statusCode = 404;
            res.end("Not found");
            return;
          }
          res.setHeader(
            "Content-Type",
            CONTENT_TYPES[path.extname(target)] ?? "application/octet-stream",
          );
          fs.createReadStream(target).pipe(res);
          return;
        }

        next();
      });
    },
  };
}

export default defineConfig({
  root: path.join(__dirname, "editor"),
  plugins: [react(), projectApiPlugin()],
  server: {
    port: 5173,
  },
  resolve: {
    alias: {
      // Editor shares the exact same source as the CLI pipeline.
      "@core": path.join(__dirname, "src"),
    },
  },
});
