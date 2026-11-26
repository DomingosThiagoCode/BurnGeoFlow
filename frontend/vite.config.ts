import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
  },
  build: {
    target: "es2022",
    sourcemap: false,
    rollupOptions: {
      // Entradas separadas. O atlas científico permanece em /;
      // a narrativa fica em /apresentacao/.
      input: {
        atlas: fileURLToPath(new URL("./index.html", import.meta.url)),
        apresentacao: fileURLToPath(new URL("./apresentacao/index.html", import.meta.url)),
      },
    },
  },
});