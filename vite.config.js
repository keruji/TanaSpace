import { defineConfig } from "vite";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [tailwindcss()],
  build: {
    watch: process.env.CHOKIDAR_USEPOLLING === "true"
      ? { watcher: { usePolling: true, pollInterval: 300 } }
      : null,
    rollupOptions: {
      input: "src/main.js",
      output: {
        entryFileNames: "app.js",
        assetFileNames: "app[extname]",
      },
    },
  },
});
