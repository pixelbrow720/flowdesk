/**
 * Cross-language validation harness for the Snapshot contract (TypeScript side).
 *
 * Loads the shared fixtures from `../examples` and asserts:
 *   - snapshot.example.json   is ACCEPTED
 *   - snapshot.malformed.json is REJECTED
 *
 * Run: `pnpm --filter @flowdesk/contracts validate`
 */
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { safeParseSnapshot } from "../src/index";

const here = dirname(fileURLToPath(import.meta.url));

function load(name: string): unknown {
  return JSON.parse(
    readFileSync(resolve(here, "..", "examples", name), "utf8"),
  ) as unknown;
}

let ok = true;

const good = safeParseSnapshot(load("snapshot.example.json"));
console.log(
  `snapshot.example.json   -> ${good.success ? "ACCEPTED" : "REJECTED"}`,
);
if (!good.success) {
  ok = false;
  console.error(good.error.issues);
}

const bad = safeParseSnapshot(load("snapshot.malformed.json"));
console.log(
  `snapshot.malformed.json -> ${bad.success ? "ACCEPTED" : "REJECTED"}`,
);
if (bad.success) {
  ok = false;
  console.error("ERROR: malformed fixture should have been rejected");
} else {
  console.log(`  reason: ${bad.error.issues.map((i) => i.message).join("; ")}`);
}

process.exit(ok ? 0 : 1);
