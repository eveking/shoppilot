import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 开发模式代理到本地 ShopPilot 服务；生产构建产物由 FastAPI 静态托管
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/sessions": "http://localhost:8000",
      "/chat": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
});
