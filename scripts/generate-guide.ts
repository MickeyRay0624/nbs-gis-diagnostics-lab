import { copyFile } from "node:fs/promises";

// Keep the GitHub manual and the website download identical.
await copyFile(
  new URL("../docs/user-guide.en.md", import.meta.url),
  new URL("../public/guide.en.md", import.meta.url),
);

await copyFile(
  new URL("../docs/local-preparation.en.md", import.meta.url),
  new URL("../public/local-preparation.en.md", import.meta.url),
);
