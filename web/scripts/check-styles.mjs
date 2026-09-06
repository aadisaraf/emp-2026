// Constitution lint for the PullSheet dashboard (web/).
// Scans every stylesheet for anti-slop violations and fails loudly.
// Usage: node scripts/check-styles.mjs [--file <relative-or-absolute-path>]
// Exit 0 = clean, exit 1 = violations found.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(here, "..");
const tokensPath = path.join(webRoot, "src", "styles", "tokens.css");

const tokensCss = fs.readFileSync(tokensPath, "utf8");
const defined = new Set([...tokensCss.matchAll(/--([\w-]+)\s*:/g)].map((m) => m[1]));

// The only permitted gradient and shadow in the codebase (documented exceptions).
const EXCEPTIONS = [
  { file: "RunDayStrip.module.css", pattern: "repeating-linear-gradient" },
  { file: "DataTable.module.css", pattern: "0 1px 0 0" },
];

function isExcepted(file, line) {
  return EXCEPTIONS.some((e) => file.endsWith(e.file) && line.includes(e.pattern));
}

function walk(dir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === "node_modules" || entry.name === ".next") continue;
      walk(full, out);
    } else if (entry.name.endsWith(".css")) {
      out.push(full);
    }
  }
  return out;
}

const EMOJI_RE =
  /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{2B00}-\u{2BFF}\u{FE0F}]/u;
const ALLOWED_PX = new Set([11, 13, 15, 20]);

let files = walk(path.join(webRoot, "src"));
files.push(tokensPath);
const fileFlag = process.argv.indexOf("--file");
if (fileFlag !== -1 && process.argv[fileFlag + 1]) {
  const only = path.resolve(webRoot, process.argv[fileFlag + 1]);
  files = files.filter((f) => path.resolve(f) === only);
  if (files.length === 0) {
    console.error(`No stylesheet matches --file ${process.argv[fileFlag + 1]}`);
    process.exit(2);
  }
}

const hits = [];
function hit(file, line, rule, detail) {
  hits.push({ file: path.relative(webRoot, file), line, rule, detail });
}

for (const file of files) {
  const text = fs.readFileSync(file, "utf8");
  const lines = text.split("\n");
  lines.forEach((raw, i) => {
    const lineNo = i + 1;
    const line = raw;
    // (a) undefined var(--x)
    for (const m of line.matchAll(/var\(--([\w-]+)/g)) {
      if (!defined.has(m[1])) {
        hit(file, lineNo, "undefined-token", `var(--${m[1]}) not defined in tokens.css :: ${line.trim()}`);
      }
    }
    // (b) bare font-weight outside 400/600 (tokens or literals)
    const fw = line.match(/font-weight\s*:\s*([^;]+);?/);
    if (fw && !/var\(--weight-(normal|strong)\)/.test(fw[1])) {
      const v = fw[1].trim();
      if (v !== "400" && v !== "600") {
        hit(file, lineNo, "bare-font-weight", `font-weight: ${v} (use var(--weight-normal) or var(--weight-strong))`);
      } else {
        hit(file, lineNo, "bare-font-weight", `literal font-weight: ${v} (use the token)`);
      }
    }
    // (c) font-size px outside the 5-size scale
    for (const m of line.matchAll(/font-size\s*:\s*([\d.]+)px/g)) {
      if (!ALLOWED_PX.has(Number(m[1]))) {
        hit(file, lineNo, "off-scale-type", `font-size: ${m[1]}px (scale is 11/13/15/20)`);
      }
    }
    // (d) border-radius px above 3
    for (const m of line.matchAll(/(?:border-radius|border-[\w-]+-radius)\s*:\s*([\d.]+)px/g)) {
      if (Number(m[1]) > 3) {
        hit(file, lineNo, "radius-above-3px", `radius ${m[1]}px (nothing above 3px)`);
      }
    }
    // (e) banned constructs outside documented exceptions
    if (!isExcepted(file, line)) {
      if (/box-shadow\s*:/.test(line)) hit(file, lineNo, "banned-shadow", line.trim());
      if (/linear-gradient|radial-gradient/.test(line)) hit(file, lineNo, "banned-gradient", line.trim());
      if (/(^|[\s{;])opacity\s*:/.test(line)) hit(file, lineNo, "banned-opacity", line.trim());
      if (/backdrop-filter\s*:/.test(line)) hit(file, lineNo, "banned-translucency", line.trim());
    }
    // (f) font-family outside tokens
    if (/font-family\s*:/.test(line) && !/var\(--font-(ui|mono)\)/.test(line)) {
      hit(file, lineNo, "bare-font-family", line.trim());
    }
    // (g) emoji
    if (EMOJI_RE.test(line)) {
      hit(file, lineNo, "emoji", line.trim());
    }
  });
}

if (hits.length === 0) {
  console.log("check-styles: clean — 0 violations.");
  process.exit(0);
}

console.log(`check-styles: ${hits.length} violation(s):`);
for (const h of hits) {
  console.log(`  ${h.file}:${h.line} [${h.rule}] ${h.detail}`);
}
process.exit(1);
