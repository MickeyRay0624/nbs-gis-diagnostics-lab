import { writeFile } from "node:fs/promises";

// Browser sessions belong to the same HTTPS site as the compute service.
// Keep old shared Pages links useful without creating a second workspace host.
const workspace = "https://lmqstudio.com/nbs/";
await writeFile(new URL("../dist-pages/index.html", import.meta.url), `<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="0; url=${workspace}">
  <link rel="canonical" href="${workspace}">
  <title>NbS Diagnostics Lab</title>
  <style>
    body { margin: 0; min-height: 100vh; display: grid; place-items: center; background: #f3f5ee; color: #123b35; font: 18px/1.6 system-ui, sans-serif; }
    main { max-width: 38rem; padding: 3rem 1.5rem; }
    h1 { font-size: clamp(2rem, 5vw, 3rem); line-height: 1.15; }
    a { color: #15574a; }
    .action { display: inline-block; padding: .75rem 1.5rem; border-radius: .75rem; color: white; background: #15574a; text-decoration: none; }
  </style>
</head>
<body>
  <main>
    <p>NATURE-BASED SOLUTIONS · EIGHT DIAGNOSTICS</p>
    <h1>Your landscape workspace is ready.</h1>
    <p>Choose an area, run an analysis online, and explore your results.</p>
    <p><a class="action" href="${workspace}">Open NbS Diagnostics Lab →</a></p>
    <p><a href="guide.en.md">English user manual</a> · <a href="https://github.com/MickeyRay0624/nbs-gis-diagnostics-lab">Source code</a></p>
  </main>
</body>
</html>
`);
console.log(`GitHub Pages entry points to ${workspace}`);
