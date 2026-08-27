/// <reference types="vitest/config" />
import path from "path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// Адрес бэкенда различается: с хоста это 127.0.0.1:8002, внутри сети
// контейнеров — backend:8000. В сборку он не попадает: прокси работает только
// на dev-сервере, а в проде фронтенд и API отдаёт один Caddy с одного адреса.
const apiTarget = process.env.VITE_API_TARGET ?? "http://127.0.0.1:8002"

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
      "/api": { target: apiTarget, changeOrigin: true },
      "/healthz": { target: apiTarget, changeOrigin: true },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/shared/lib/test-setup.ts"],
  },
})
