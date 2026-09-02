#!/usr/bin/env node
// PreToolUse(Read): hand the model a downscaled copy of an image, never the original.
//
// Images read at full size are the single largest cost in a long conversation.
// Eleven photos read in one turn came to 1.9 MB, and an image stays in the
// transcript — so every later turn pays for them again. A 1024px copy is enough
// to see what a photo is, place it, or check a layout.
//
// Same shape as the rtk hook beside it: rewrite the tool's input and let the
// tool run normally. Silence on any problem — a hook that breaks Read is far
// worse than a large image.

import { execFileSync } from "node:child_process";
import { mkdirSync, statSync } from "node:fs";
import { basename, join } from "node:path";
import { tmpdir } from "node:os";

const MAX_EDGE = 1024;
// Below this, downscaling saves little and costs a subprocess.
const MIN_BYTES = 200 * 1024;
const EXT = /\.(png|jpe?g|webp|gif|bmp|tiff?)$/i;

let raw = "";
process.stdin.on("data", (c) => (raw += c));
process.stdin.on("end", () => {
  let input = {};
  try {
    input = JSON.parse(raw || "{}");
  } catch {
    process.exit(0);
  }

  const path = input?.tool_input?.file_path;
  if (input?.tool_name !== "Read" || typeof path !== "string" || !EXT.test(path)) {
    process.exit(0);
  }

  let size = 0;
  try {
    size = statSync(path).size;
  } catch {
    process.exit(0); // let Read report the missing file itself
  }
  if (size < MIN_BYTES) process.exit(0);

  const outDir = join(tmpdir(), "agent-downscaled");
  // Always WebP: a 1024px photo lands around 60-120 KB instead of megabytes,
  // and Claude Code reads WebP natively.
  const out = join(outDir, `${MAX_EDGE}-${basename(path).replace(EXT, "")}.webp`);
  try {
    mkdirSync(outDir, { recursive: true });
    shrink(path, out);
    statSync(out);
  } catch {
    process.exit(0); // original is still readable; better a big image than none
  }

  process.stdout.write(
    JSON.stringify({
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecisionReason: `downscaled to ${MAX_EDGE}px (was ${Math.round(size / 1024)} KB)`,
        updatedInput: { ...input.tool_input, file_path: out },
      },
    })
  );
  process.exit(0);
});

function shrink(src, dst) {
  // Pillow where it exists (the container), sips on macOS. Both cap the long
  // edge and preserve aspect ratio.
  try {
    execFileSync(
      "python3",
      [
        "-c",
        `import sys
from PIL import Image
im = Image.open(sys.argv[1])
im.thumbnail((${MAX_EDGE}, ${MAX_EDGE}))
im.convert("RGB").save(sys.argv[2], "WEBP", quality=80, method=4)`,
        src,
        dst,
      ],
      { stdio: "ignore", timeout: 20000 }
    );
    return;
  } catch {
    // fall through to sips
  }
  // macOS fallback: sips writes WebP on recent versions.
  execFileSync("sips", ["-s", "format", "webp", "-Z", String(MAX_EDGE), src, "--out", dst], {
    stdio: "ignore",
    timeout: 20000,
  });
}
