import { mkdir, copyFile } from "node:fs/promises";
await mkdir("dist/api-docs", { recursive: true });
for (const file of ["swagger-ui-bundle.js", "swagger-ui.css", "LICENSE"]) {
  await copyFile(
    `node_modules/swagger-ui-dist/${file}`,
    `dist/api-docs/${file}`,
  );
}
