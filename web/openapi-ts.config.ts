import { defineConfig } from "@hey-api/openapi-ts";

// Regenerate after backend API changes:
//   (repo root) uv run python -m src.export_openapi   ->  web/openapi.json
//   (web/)      pnpm api:generate
export default defineConfig({
  input: "./openapi.json",
  output: { path: "src/lib/api/generated" },
  plugins: [
    { name: "@hey-api/client-fetch", runtimeConfigPath: "@/lib/api/runtime-config" },
    "@tanstack/react-query",
  ],
});
