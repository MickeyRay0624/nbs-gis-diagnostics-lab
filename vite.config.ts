import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const repositoryName =
  process.env.GITHUB_REPOSITORY?.split("/")[1] ?? "nbs-gis-diagnostics-lab";
const base = process.env.GITHUB_ACTIONS === "true" ? `/${repositoryName}/` : "/";

export default defineConfig({
  base,
  plugins: [react()],
  build: {
    outDir: "dist-pages",
    emptyOutDir: true,
  },
});
