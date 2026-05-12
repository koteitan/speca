import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

// Vite dev config:
// - alias `@/...` -> `src/...` to match tsconfig `paths`
// - proxy /api -> FastAPI on 127.0.0.1:7411 so the SPA can talk to the
//   backend without CORS during development
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
      },
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    sourcemap: true,
  },
});
