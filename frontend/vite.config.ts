/// <reference types="vitest/config" />
import path from "path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
    },
  },
  server: {
    port: 3002,
    // Браузер видит фронтенд и API на одном адресе — так же, как в проде за
    // Caddy. Поэтому не нужен ни CORS, ни разрешение кук между источниками,
    // ни переменная с адресом бэкенда: запросы идут относительными путями.
    proxy: {
      "/api": { target: "http://127.0.0.1:8002", changeOrigin: true },
      "/healthz": { target: "http://127.0.0.1:8002", changeOrigin: true },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/shared/lib/test-setup.ts"],
  },
})
