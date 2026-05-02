import path from "node:path";
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

const staticOut = path.resolve(__dirname, "../src/flightdeck/server/static");

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, __dirname, "");
  const proxyTarget = env.VITE_DEV_PROXY_TARGET || "http://127.0.0.1:8765";

  return {
    plugins: [react()],
    base: "/",
    server: {
      port: 5173,
      proxy: {
        "/v1": { target: proxyTarget, changeOrigin: true },
        "/health": { target: proxyTarget, changeOrigin: true },
      },
    },
    build: {
      outDir: staticOut,
      emptyOutDir: true,
      assetsDir: "assets",
      rollupOptions: {
        output: {
          assetFileNames: "assets/[name]-[hash][extname]",
          chunkFileNames: "assets/[name]-[hash].js",
          entryFileNames: "assets/[name]-[hash].js",
        },
      },
    },
  };
});
