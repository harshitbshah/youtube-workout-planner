// Run with: node scripts/generate-icons.mjs
import sharp from "sharp";
import { readFileSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = resolve(__dirname, "..");
const svgPath = resolve(root, "public/icons/icon.svg");
const svgBuffer = readFileSync(svgPath);

const sizes = [
  { name: "icon-192.png", size: 192 },
  { name: "icon-512.png", size: 512 },
  // Maskable icons use the same SVG but the background fills the safe zone
  { name: "icon-maskable-192.png", size: 192 },
  { name: "icon-maskable-512.png", size: 512 },
];

for (const { name, size } of sizes) {
  const outPath = resolve(root, "public/icons", name);
  await sharp(svgBuffer)
    .resize(size, size)
    .png()
    .toFile(outPath);
  console.log(`✓ Generated ${name} (${size}x${size})`);
}

console.log("\nAll icons generated successfully.");
