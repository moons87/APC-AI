import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Порт 5173 пробрасывается в docker-compose.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    // Разрешаем доступ по любому хосту (нужно для записи из контейнера по имени frontend).
    allowedHosts: true,
  },
});
