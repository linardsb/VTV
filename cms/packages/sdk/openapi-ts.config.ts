import { defineConfig } from "@hey-api/openapi-ts";

export default defineConfig({
  input: "http://localhost:8123/openapi.json",
  output: {
    path: "./src/client",
    format: "prettier",
  },
  plugins: [
    "@hey-api/typescript",
    {
      name: "@hey-api/sdk",
      transformer: true,
    },
  ],
});
