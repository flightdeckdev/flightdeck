/**
 * Normalize built assets under src/flightdeck/server/static/ after Vite build.
 * - CRLF -> LF (Windows vs CI)
 * - index.html: collapse extra blank lines before </body> (Vite 7.3+ adds one;
 *   CI uses git diff --exit-code on static/)
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const staticDir = path.resolve(__dirname, "..", "..", "src", "flightdeck", "server", "static");

function normalizeFile(filePath) {
  const buf = fs.readFileSync(filePath);
  if (buf.includes(0)) return;
  const s = buf.toString("utf8");
  let out = s.replace(/\r\n/g, "\n").replace(/\r/g, "\n");
  if (path.basename(filePath) === "index.html") {
    out = out.replace(/(<div id="root"><\/div>)\n\n+(\s*<\/body>)/, "$1\n$2");
  }
  if (out !== s) fs.writeFileSync(filePath, out, "utf8");
}

function walk(dir) {
  if (!fs.existsSync(dir)) return;
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, ent.name);
    if (ent.isDirectory()) walk(p);
    else normalizeFile(p);
  }
}

walk(staticDir);
