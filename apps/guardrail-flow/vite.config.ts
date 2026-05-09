import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    strictPort: false,
    host: "127.0.0.1",
  },
  preview: {
    port: 4173,
    strictPort: false,
    host: "127.0.0.1",
  },
  build: {
    outDir: "dist",
    sourcemap: true,
    target: "es2022",
  },
});
