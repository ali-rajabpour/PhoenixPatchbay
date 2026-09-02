#!/usr/bin/env node
// PreToolUse(Read): two guardrails on the files a user hands the agent.
//
// 1. CONSENT. Contents are not extracted unless the user asked for that. A file
//    sent to a topic is usually meant to be placed, attached, moved or linked —
//    not read. One curious Read of a PDF that only needed uploading cost
//    629 KB of transcript, and a transcript is re-sent on every later turn, so
//    that single read was paid for again and again for the rest of the session.
//
// 2. CHEAP COPY. When reading *is* wanted, the model still gets a small
//    version: images become a 1024px WebP, PDFs become extracted text. The
//    picture is legible and the text is exact; the megabytes are not.
//
// Everything except the consent gate fails open. A hook that breaks Read is
// worse than a large file, so any unexpected error lets the original through.

import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, statSync, writeFileSync } from "node:fs";
import { basename, join } from "node:path";
import { tmpdir } from "node:os";

const MAX_EDGE = 1024;
// Below this, downscaling saves less than the subprocess costs.
const MIN_BYTES = 200 * 1024;
// Extracted PDF text is exact, so the only risk is length. A contract runs a
// few tens of KB; past this it is a book and should be read in pieces.
const MAX_TEXT_BYTES = 120 * 1024;
// Fewer characters than this means no text layer — a scan, not a document.
const MIN_TEXT_CHARS = 200;

const IMAGE_EXT = /\.(png|jpe?g|webp|gif|bmp|tiff?)$/i;
const PDF_EXT = /\.pdf$/i;

// Consent is a file the agent touches after the user says yes. Named after the
// document rather than a hash so the instruction we print can be pasted as-is;
// two different files with one name is a collision worth trading for that.
const APPROVED_DIR = join(tmpdir(), "agent-read-approved");
const approvalPath = (p) => join(APPROVED_DIR, basename(p));

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
  if (input?.tool_name !== "Read" || typeof path !== "string") process.exit(0);

  const isImage = IMAGE_EXT.test(path);
  const isPdf = PDF_EXT.test(path);
  if (!isImage && !isPdf) process.exit(0);

  try {
    statSync(path);
  } catch {
    process.exit(0); // let Read report the missing file itself
  }

  if (!existsSync(approvalPath(path))) {
    deny(
      `Reading the contents of ${basename(path)} needs the user's say-so.\n` +
        `If they asked you to place, attach, upload, move or link this file, you do not need to read it — carry on without it.\n` +
        `If they asked what is inside it, ask them to confirm, then run:\n` +
        `  mkdir -p ${APPROVED_DIR} && touch ${approvalPath(path)}\n` +
        `and read it again. Do not run that command on your own initiative.`
    );
  }

  const size = statSync(path).size;

  if (isPdf) {
    const text = pdfText(path);
    if (text === null || text.length < MIN_TEXT_CHARS) {
      // No text layer: a scan. The user has approved this read, so let the
      // original through rather than second-guessing an explicit instruction.
      process.exit(0);
    }
    const out = join(APPROVED_DIR, `${basename(path)}.txt`);
    try {
      writeFileSync(out, text.slice(0, MAX_TEXT_BYTES), "utf8");
    } catch {
      process.exit(0);
    }
    rewrite(
      input,
      out,
      `PDF text extracted (${Math.round(size / 1024)} KB file -> ${Math.round(text.length / 1024)} KB text)`
    );
  }

  if (size < MIN_BYTES) process.exit(0);

  const out = join(tmpdir(), "agent-downscaled", `${MAX_EDGE}-${basename(path).replace(IMAGE_EXT, "")}.webp`);
  try {
    mkdirSync(join(tmpdir(), "agent-downscaled"), { recursive: true });
    shrink(path, out);
    statSync(out);
  } catch {
    process.exit(0); // original is still readable; better a big image than none
  }
  rewrite(input, out, `downscaled to ${MAX_EDGE}px (was ${Math.round(size / 1024)} KB)`);
});

function deny(reason) {
  process.stdout.write(
    JSON.stringify({
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "deny",
        permissionDecisionReason: reason,
      },
    })
  );
  process.exit(0);
}

function rewrite(input, file, reason) {
  process.stdout.write(
    JSON.stringify({
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecisionReason: reason,
        updatedInput: { ...input.tool_input, file_path: file },
      },
    })
  );
  process.exit(0);
}

function pdfText(src) {
  // poppler-utils. Absent on a machine without it, which is why the caller
  // treats null as "hand over the original".
  try {
    return execFileSync("pdftotext", ["-q", "-enc", "UTF-8", src, "-"], {
      encoding: "utf8",
      timeout: 30000,
      maxBuffer: 64 * 1024 * 1024,
    });
  } catch {
    return null;
  }
}

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
