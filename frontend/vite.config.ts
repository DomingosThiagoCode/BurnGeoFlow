import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Caminho file:// convertido para URL local, inclusive em Windows, sem exigir @types/node.
const pagina = (relative: string) => decodeURIComponent(new URL(relative, import.meta.url).pathname)
  .replace(/^\/([A-Za-z]:\/)/, "$1");

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
        atlas: pagina("./index.html"),
        apresentacao: pagina("./apresentacao/index.html"),
      },
    },
  },
});