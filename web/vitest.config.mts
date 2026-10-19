import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["./vitest.setup.ts"],
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"],
      // Route pages and the layout are server components; Playwright (e2e/) covers them.
      exclude: ["src/**/*.test.{ts,tsx}", "src/test/**", "src/app/**/page.tsx", "src/app/layout.tsx"],
      reporter: ["text-summary", "json-summary"],
      thresholds: { lines: 85, statements: 85, functions: 80, branches: 80 },
    },
  },
});
