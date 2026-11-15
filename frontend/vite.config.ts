/// <reference types="vitest/config" />
import { defineConfig, loadEnv, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

// Replay build: one classic script so dist-replay/index.html opens from file:// (Req. 35.5).
const classicScript = (): Plugin => ({
  name: "replay-classic-script",
  enforce: "post",
  transformIndexHtml: (html) => html.replace(/<script type="module" crossorigin/g, "<script defer"),
});

// Local dev against the deployed stack (opt-in): copy .env.local.example to .env.local.
// The dev server then serves /config.json from it and proxies /api to the Session_API,
// so the browser stays same-origin and the API's CORS rule (Amplify origin only) is not hit.
const localStack = (env: Record<string, string>): Plugin => ({
  name: "local-stack-config",
  configureServer(server) {
    if (!env.GUIDE_API_URL) return;
    const body = JSON.stringify({
      apiUrl: "/api",
      region: env.GUIDE_REGION || "us-east-1",
      userPoolId: env.GUIDE_USER_POOL_ID,
      userPoolClientId: env.GUIDE_USER_POOL_CLIENT_ID,
    });
    server.middlewares.use("/config.json", (_req, res) => {
      res.setHeader("Content-Type", "application/json");
      res.end(body);
    });
  },
});

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "GUIDE_");
  return mode === "replay" ? {
  base: "./",
  plugins: [react(), classicScript()],
  publicDir: false,
  build: {
    outDir: "dist-replay",
    modulePreload: false,
    rollupOptions: { output: { format: "iife", inlineDynamicImports: true } },
  },
} : {
  plugins: [react(), localStack(env)],
  server: env.GUIDE_API_URL ? {
    proxy: {
      "/api": {
        target: env.GUIDE_API_URL.replace(/\/+$/, ""),
        changeOrigin: true,
        rewrite: (path: string) => path.replace(/^\/api/, ""),
      },
    },
  } : undefined,
  test: { environment: "jsdom", globals: true, setupFiles: ["./src/setupTests.ts"] },
};
});
