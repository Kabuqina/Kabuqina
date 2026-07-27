import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwind from "@tailwindcss/vite";

// Kabuqina web shell. The Tauri window initially loads this static
// app (which runs the onboarding wizard if needed, then redirects to
// the local dashboard server on http://127.0.0.1:PORT).
export default defineConfig({
  plugins: [react(), tailwind()],
  clearScreen: false,
  server: {
    // 允许外部指定端口（并行开第二个 dev server 时用）；未指定仍是 5173。
    port: Number(process.env.PORT) || 5173,
    strictPort: true,
  },
  build: {
    target: "esnext",
    sourcemap: false,
  },
});
