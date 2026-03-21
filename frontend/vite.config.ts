import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: (process.env as any).VITE_API_URL ?? "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
