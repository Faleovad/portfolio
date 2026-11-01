import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: process.env.API_PROXY || "http://127.0.0.1:58042",
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
      "/lab": {
        target: process.env.CONTROL_PROXY || "http://127.0.0.1:58043",
        rewrite: (p) => p.replace(/^\/lab/, ""),
      },
    },
  },
});
