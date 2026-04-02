const fs = require("fs");
const path = require("path");

const buildDir = path.join(__dirname, "..", "build");
const indexPath = path.join(buildDir, "index.html");
const errorPath = path.join(buildDir, "404.html");

if (!fs.existsSync(indexPath)) {
  console.error("index.html was not found in build output.");
  process.exit(1);
}

fs.copyFileSync(indexPath, errorPath);
console.log("Copied build/index.html to build/404.html");
