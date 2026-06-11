import { defineConfig } from "vitest/config";

// Unit tests for the realtime layer (pure reducer + fake-socket client). Node
// environment; the @flowdesk/contracts workspace package resolves via its
// node_modules symlink (vitest transpiles its TS source through esbuild).
export default defineConfig({
  test: {
    environment: "node",
    include: ["lib/**/*.test.ts"],
  },
});
