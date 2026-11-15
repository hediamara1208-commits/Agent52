/// <reference types="vitest/config" />
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

// Replay build: one classic script so dist-replay/index.html opens from file:// (Req. 35.5).
const classicScript = (): Plugin => ({
  name: "replay-classic-script",
  enforce: "post",
  transformIndexHtml: (html) => html.replace(/<script type="module" crossorigin/g, "<script defer"),
});

export default defineConfig(({ mode }) => mode === "replay" ? {
  base: "./",
  plugins: [react(), classicScript()],
  publicDir: false,
  build: {
    outDir: "dist-replay",
    modulePreload: false,
    rollupOptions: { output: { format: "iife", inlineDynamicImports: true } },
  },
} : {
  plugins: [react()],
  test: { environment: "jsdom", globals: true, setupFiles: ["./src/setupTests.ts"] },
});
