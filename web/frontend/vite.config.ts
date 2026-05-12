import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

// Vite dev config:
// - alias `@/...` -> `src/...` to match tsconfig `paths`
// - proxy /api -> FastAPI on 127.0.0.1:7411 so the SPA can talk to the
//   backend without CORS during development
// - `ws: true` upgrades `/api/ws/...` automatically; the same proxy entry
//   handles both HTTP (REST) and the WebSocket sub-tree (Slice D1).
// - emit a static build to `dist` which `speca-web --serve-frontend` mounts
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:7411",
        changeOrigin: false,
        // Enable WebSocket proxying so `ws://127.0.0.1:5173/api/ws/...`
        // is forwarded to `ws://127.0.0.1:7411/api/ws/...`. Vite's
        // http-proxy auto-handles the Upgrade handshake when this is set.
        ws: true,
      },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    sourcemap: true,
  },
});
