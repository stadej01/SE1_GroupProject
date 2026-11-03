import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Django owns HTML and routing. Vite only produces static JS/CSS and a manifest.
export default defineConfig({
  plugins: [react()],
  base: "./",
  build: {
    outDir: "../backend/editor/static/editor/dist",
    emptyOutDir: true,
    manifest: "manifest.json",
    rollupOptions: { input: "src/main.tsx" },
  },
});
