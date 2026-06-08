import fs from "node:fs/promises";
import fsSync from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { createRequire } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";

const runtimeRequire = createRequire(
  "C:\\Users\\X13\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\node_modules\\.pnpm\\playwright@1.60.0\\node_modules\\playwright\\package.json",
);
const { chromium } = runtimeRequire("playwright");

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const HTML_DIR = path.join(ROOT, "neo-grid-bold_html");
const HTML_FILE = path.join(HTML_DIR, "template.html");
const BACKGROUND_DIR = path.join(ROOT, "backgrounds");
const TEXT_LAYER_PATH = path.join(ROOT, "text-layer.json");
const PREVIEW_PATH = path.join(ROOT, "preview.png");
const OUTPUT_PPTX = path.join(ROOT, "template.pptx");

const BUILD_ROOT = path.resolve("outputs/manual-20260608-neo-grid-bold/presentations/html-background-master");
const SLIDES_DIR = path.join(BUILD_ROOT, "slides");
const PREVIEW_DIR = path.join(BUILD_ROOT, "preview");
const LAYOUT_DIR = path.join(BUILD_ROOT, "layout");

const SKILL_DIR = "C:\\Users\\X13\\.codex\\plugins\\cache\\openai-primary-runtime\\presentations\\26.601.10930\\skills\\presentations";
const BUILD_SCRIPT = path.join(SKILL_DIR, "scripts", "build_artifact_deck.mjs");
const NODE = "C:\\Users\\X13\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\node\\bin\\node.exe";
const PYTHON = "C:\\Users\\X13\\.cache\\codex-runtimes\\codex-primary-runtime\\dependencies\\python\\python.exe";
const MAGICK = "C:\\Program Files\\ImageMagick-7.1.2-Q16-HDRI\\magick.exe";

const VIEWPORT = { width: 1920, height: 1080 };
const SLIDE = { width: 1280, height: 720 };
const SCALE_X = SLIDE.width / VIEWPORT.width;
const SCALE_Y = SLIDE.height / VIEWPORT.height;

function toPosixPath(value) {
  return value.replace(/\\/g, "/");
}

function quoteJs(value) {
  return JSON.stringify(toPosixPath(value));
}

function normalizeFont(fontFamily) {
  const value = String(fontFamily || "");
  if (value.includes("Space Grotesk")) return "Space Grotesk";
  if (value.includes("JetBrains Mono")) return "JetBrains Mono";
  return "Space Grotesk";
}

function fontSizePt(px) {
  const n = Number.parseFloat(px || "16");
  return Math.max(6, Math.round(n * 0.75 * 10) / 10);
}

async function ensureCleanDir(dir) {
  await fs.rm(dir, { recursive: true, force: true });
  await fs.mkdir(dir, { recursive: true });
}

async function renderHtml() {
  await fs.mkdir(BACKGROUND_DIR, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: VIEWPORT, deviceScaleFactor: 1 });
  await page.goto(pathToFileURL(HTML_FILE).href, { waitUntil: "networkidle" });
  await page.evaluate(async () => {
    await customElements.whenDefined("deck-stage");
    if (document.fonts?.ready) await document.fonts.ready;
    const stage = document.querySelector("deck-stage");
    stage?.setAttribute("noscale", "");
    stage?.setAttribute("no-rail", "");
    stage?.shadowRoot?.querySelectorAll(".overlay, .tapzones, .rail, .rail-shell").forEach((el) => {
      el.style.setProperty("display", "none", "important");
      el.style.setProperty("visibility", "hidden", "important");
      el.style.setProperty("opacity", "0", "important");
    });
    const style = document.createElement("style");
    style.textContent = `
      deck-stage,
      deck-stage * {
        transition: none !important;
        animation: none !important;
      }
      [data-anim] {
        opacity: 1 !important;
        transform: none !important;
        clip-path: none !important;
      }
      .pagenum,
      .meta-l,
      .label,
      .tag,
      .role,
      .yearlabel,
      .legend .li,
      .xaxis span,
      .yticks,
      .xticks,
      .src,
      .timeline,
      .timeline span,
      .s-system .panel h4,
      .s-system .panel p,
      .s-system .panel li,
      .s-system .sw,
      .s-system .lbl,
      .s-chart2 .pane-r .yhead,
      .s-process2 .node .n,
      .s-matrix2 .table .head-row {
        font-size: max(16px, 1em) !important;
        line-height: 1.34 !important;
      }
      p,
      li,
      .sub,
      .feat p,
      .step p,
      .node p,
      .s-consult .col p,
      .s-consult .col ul,
      .s-consult .col ul li,
      .s-chart2 .pane-l p {
        font-size: max(19px, 1em) !important;
        line-height: 1.42 !important;
      }
    `;
    document.head.appendChild(style);
  });

  const slideCount = await page.evaluate(() => document.querySelector("deck-stage")?.length || 0);
  const slides = [];

  for (let index = 0; index < slideCount; index += 1) {
    const slideNo = String(index + 1).padStart(2, "0");
    const backgroundPath = path.join(BACKGROUND_DIR, `slide-${slideNo}.png`);
    const { role, label, textLayer } = await page.evaluate(async (activeIndex) => {
      const stage = document.querySelector("deck-stage");
      stage.goTo(activeIndex);
      await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
      stage.shadowRoot?.querySelectorAll(".overlay, .tapzones, .rail, .rail-shell").forEach((el) => {
        el.style.setProperty("display", "none", "important");
        el.style.setProperty("visibility", "hidden", "important");
        el.style.setProperty("opacity", "0", "important");
      });
      const activeSlide = stage.querySelector("[data-deck-active]") || Array.from(stage.children)[activeIndex];
      const skipSelector = "script, style, svg, button, [aria-hidden='true'], .export-hidden";
      const walker = document.createTreeWalker(activeSlide, NodeFilter.SHOW_TEXT, {
        acceptNode(node) {
          const text = node.textContent.replace(/\s+/g, " ").trim();
          if (!text) return NodeFilter.FILTER_REJECT;
          const parent = node.parentElement;
          if (!parent || parent.closest(skipSelector)) return NodeFilter.FILTER_REJECT;
          const style = getComputedStyle(parent);
          if (style.display === "none" || style.visibility === "hidden" || Number(style.opacity) === 0) {
            return NodeFilter.FILTER_REJECT;
          }
          return NodeFilter.FILTER_ACCEPT;
        },
      });

      const items = [];
      while (walker.nextNode()) {
        const node = walker.currentNode;
        const text = node.textContent.replace(/\s+/g, " ").trim();
        const range = document.createRange();
        range.selectNodeContents(node);
        const rect = range.getBoundingClientRect();
        const parent = node.parentElement;
        const style = getComputedStyle(parent);
        if (rect.width < 2 || rect.height < 2) continue;
        items.push({
          text,
          x: rect.x,
          y: rect.y,
          width: rect.width,
          height: rect.height,
          fontFamily: style.fontFamily,
          fontSize: style.fontSize,
          fontWeight: style.fontWeight,
          color: style.color,
          textAlign: style.textAlign,
          lineHeight: style.lineHeight,
          tagName: parent.tagName.toLowerCase(),
          className: parent.className || "",
        });
      }

      const className = Array.from(activeSlide.classList).find((name) => name !== "slide") || "body";
      return {
        role: className.replace(/^s-/, "").replace(/-/g, "_"),
        label: activeSlide.getAttribute("data-label") || activeSlide.getAttribute("data-screen-label") || "",
        textLayer: items,
      };
    }, index);

    await page.screenshot({ path: backgroundPath, fullPage: false });
    slides.push({
      slide: index + 1,
      role,
      label,
      background: path.relative(ROOT, backgroundPath).replace(/\\/g, "/"),
      text_boxes: textLayer,
    });
  }

  await browser.close();
  return slides;
}

function rgbToHex(value) {
  const match = String(value || "").match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/i);
  if (!match) return "#111111";
  return `#${[match[1], match[2], match[3]]
    .map((part) => Number(part).toString(16).padStart(2, "0"))
    .join("")}`;
}

async function writeSlideModules(slides) {
  await ensureCleanDir(SLIDES_DIR);
  for (const slide of slides) {
    const slideNo = String(slide.slide).padStart(2, "0");
    const backgroundPath = path.join(ROOT, slide.background);
    const textCalls = slide.text_boxes
      .map((box, index) => {
        const x = Math.max(0, box.x * SCALE_X);
        const y = Math.max(0, box.y * SCALE_Y);
        const w = Math.min(SLIDE.width - x, Math.max(4, box.width * SCALE_X + 4));
        const h = Math.min(SLIDE.height - y, Math.max(4, box.height * SCALE_Y + 4));
        const color = `${rgbToHex(box.color)}00`;
        const fontSize = fontSizePt(box.fontSize);
        const typeface = normalizeFont(box.fontFamily);
        const bold = Number.parseInt(box.fontWeight, 10) >= 600;
        return `  ctx.addText(slide, {
    name: "editable-text-${slideNo}-${String(index + 1).padStart(2, "0")}",
    text: ${JSON.stringify(box.text)},
    x: ${round(x)}, y: ${round(y)}, w: ${round(w)}, h: ${round(h)},
    fontSize: ${fontSize},
    color: ${JSON.stringify(color)},
    bold: ${bold},
    typeface: ${JSON.stringify(typeface)},
    align: ${JSON.stringify(["center", "right"].includes(box.textAlign) ? box.textAlign : "left")},
    fill: { color: "#FFFFFF", transparency: 100 },
    insets: { left: 0, right: 0, top: 0, bottom: 0 },
  });`;
      })
      .join("\n");

    const module = `export async function slide${slideNo}(presentation, ctx) {
  const slide = presentation.slides.add();
  await ctx.addImage(slide, {
    path: ${quoteJs(backgroundPath)},
    x: 0, y: 0, w: ${SLIDE.width}, h: ${SLIDE.height},
    fit: "cover",
    alt: "Neo Grid Bold HTML-rendered background ${slideNo}",
    name: "html-background-${slideNo}",
  });
${textCalls}
  return slide;
}
`;
    await fs.writeFile(path.join(SLIDES_DIR, `slide-${slideNo}.mjs`), module, "utf8");
  }
}

function round(value) {
  return Math.round(value * 100) / 100;
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: process.cwd(),
    encoding: "utf8",
    env: {
      ...process.env,
      HOME: "C:\\Users\\X13",
      PYTHON,
    },
    ...options,
  });
  if (result.status !== 0) {
    if (args.includes(BUILD_SCRIPT) && fsSync.existsSync(OUTPUT_PPTX)) {
      return result;
    }
    throw new Error([`Command failed: ${command} ${args.join(" ")}`, result.stdout, result.stderr].filter(Boolean).join("\n"));
  }
  return result;
}

async function buildPptx(slides) {
  await fs.mkdir(PREVIEW_DIR, { recursive: true });
  await fs.mkdir(LAYOUT_DIR, { recursive: true });
  run(NODE, [
    BUILD_SCRIPT,
    "--slides-dir",
    SLIDES_DIR,
    "--out",
    OUTPUT_PPTX,
    "--preview-dir",
    PREVIEW_DIR,
    "--layout-dir",
    LAYOUT_DIR,
    "--manifest",
    path.join(BUILD_ROOT, "artifact-build-manifest.json"),
    "--slide-count",
    String(slides.length),
    "--slide-size",
    `${SLIDE.width}x${SLIDE.height}`,
    "--scale",
    "1",
  ]);
}

function removeTextBoxOutlines() {
  const script = String.raw`
import json
import re
import sys
import zipfile
from pathlib import Path

pptx = Path(sys.argv[1])
tmp = pptx.with_suffix(pptx.suffix + ".tmp")
line_pattern = re.compile(
    r'<a:ln w="0" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">.*?</a:ln>',
    re.S,
)
replacement = '<a:ln xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:noFill /></a:ln>'
changed = 0

with zipfile.ZipFile(pptx, "r") as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
    for item in zin.infolist():
        data = zin.read(item.filename)
        if re.fullmatch(r"ppt/slides/slide\d+\.xml", item.filename):
            text = data.decode("utf-8")
            text, count = line_pattern.subn(replacement, text)
            changed += count
            data = text.encode("utf-8")
        zout.writestr(item, data)

tmp.replace(pptx)
print(json.dumps({"no_fill_outlines": changed}))
`;
  run(PYTHON, ["-c", script, OUTPUT_PPTX]);
}

function createPreview(slides) {
  const previewSlides = slides.map((slide) => path.join(BACKGROUND_DIR, `slide-${String(slide.slide).padStart(2, "0")}.png`));
  run(MAGICK, [
    "montage",
    ...previewSlides,
    "-tile",
    "4x3",
    "-geometry",
    "384x216+10+10",
    "-background",
    "#ECECE8",
    PREVIEW_PATH,
  ]);
}

async function main() {
  const slides = await renderHtml();
  await fs.writeFile(
    TEXT_LAYER_PATH,
    JSON.stringify(
      {
        version: 1,
        visual_master: "neo_grid_bold",
        render_strategy: "html_background_with_editable_text_overlay",
        viewport: VIEWPORT,
        slide_size: SLIDE,
        classroom_readability: {
          target: "3m classroom projector readability",
          minimum_extracted_font_px: 16,
          body_floor_px: 19,
          label_floor_px: 16,
        },
        notes: [
          "Background images are rendered from the source HTML template.",
          "Editable text boxes are overlaid from DOM text-node coordinates with transparent text color to avoid double-rendering over the screenshot background.",
          "Deck-stage navigation chrome is not captured; the active slide is selected with the deck-stage API.",
          "Text box outlines are rewritten to DrawingML noFill for LibreOffice and WPS compatibility.",
        ],
        slides,
      },
      null,
      2,
    ),
    "utf8",
  );
  await writeSlideModules(slides);
  await buildPptx(slides);
  removeTextBoxOutlines();
  createPreview(slides);
  console.log(JSON.stringify({ slides: slides.length, output: OUTPUT_PPTX, preview: PREVIEW_PATH, textLayer: TEXT_LAYER_PATH }, null, 2));
}

main().catch((error) => {
  console.error(error.stack || error.message || String(error));
  process.exit(1);
});
