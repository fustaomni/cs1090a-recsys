import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    // Plotly's 3D bundle is one prebuilt file, already split into its own lazy chunk.
    chunkSizeWarningLimit: 1800,
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.js"],
  },
});
