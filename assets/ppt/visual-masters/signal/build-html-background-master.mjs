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
const HTML_DIR = path.join(ROOT, "signal_html");
const HTML_FILE = path.join(HTML_DIR, "template.html");
const BACKGROUND_DIR = path.join(ROOT, "backgrounds");
const TEXT_LAYER_PATH = path.join(ROOT, "text-layer.json");
const PREVIEW_PATH = path.join(ROOT, "preview.png");
const OUTPUT_PPTX = path.join(ROOT, "template.pptx");

const BUILD_ROOT = path.resolve("outputs/manual-20260608-signal/presentations/html-background-master");
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
  if (value.includes("Source Serif 4")) return "Source Serif 4";
  if (value.includes("DM Sans")) return "DM Sans";
  if (value.includes("IBM Plex Mono")) return "IBM Plex Mono";
  if (value.includes("Noto Serif SC")) return "Noto Serif SC";
  if (value.includes("Noto Sans SC")) return "Noto Sans SC";
  return "DM Sans";
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
    if (document.fonts?.ready) await document.fonts.ready;
    const style = document.createElement("style");
    style.textContent = `
      :root {
        --sz-display: 9.35vw !important;
        --sz-h1: 5.35vw !important;
        --sz-h2: 3.22vw !important;
        --sz-h3: 2.08vw !important;
        --sz-lead: 1.56vw !important;
        --sz-body: 1.18vw !important;
        --sz-caption: 0.96vw !important;
        --sz-label: 0.86vw !important;
      }
      #deck,
      .slide,
      .slide * {
        transition: none !important;
        animation: none !important;
      }
      [data-anim] {
        opacity: 1 !important;
        transform: none !important;
        clip-path: none !important;
      }
      #nav-dots,
      #slide-counter {
        display: none !important;
      }
      .slide {
        transform: none !important;
      }
      .label,
      .caption,
      .kicker,
      .slide-chrome,
      .slide-foot,
      .muted,
      .log-dt,
      .stat-4-label,
      .editorial-analysis,
      .bar-x-label,
      .chart-source,
      .pie-total,
      .vt-date {
        font-size: max(16px, 1em) !important;
        line-height: 1.38 !important;
      }
      .body,
      .lead,
      p,
      li,
      .log-dd,
      .flow-desc,
      .pyr-desc,
      .vt-body,
      .cycle-desc,
      .bar-val,
      .chart-source {
        font-size: max(18px, 1em) !important;
        line-height: 1.42 !important;
      }
      .stat-4-val,
      .flow-num,
      .cycle-num {
        line-height: 1.02 !important;
      }
      .slide--dense .slide-body,
      .slide--compare .slide-body,
      .slide--vtimeline .slide-body,
      .slide--cycle .slide-body {
        gap: max(var(--gap-sm), 1.1vh) !important;
      }
    `;
    document.head.appendChild(style);
  });

  const slideCount = await page.$$eval("section.slide", (slides) => slides.length);
  const slides = [];

  for (let index = 0; index < slideCount; index += 1) {
    const slideNo = String(index + 1).padStart(2, "0");
    const backgroundPath = path.join(BACKGROUND_DIR, `slide-${slideNo}.png`);
    const textLayer = await page.evaluate((activeIndex) => {
      const deck = document.getElementById("deck");
      const slides = Array.from(document.querySelectorAll("section.slide"));
      if (deck) {
        deck.style.transition = "none";
        deck.style.transform = `translateX(-${activeIndex * 100}vw)`;
      }
      slides.forEach((slide, i) => {
        slide.classList.toggle("is-active", i === activeIndex);
        slide.classList.toggle("active", i === activeIndex);
        slide.classList.toggle("prev", i < activeIndex);
        slide.style.opacity = i === activeIndex ? "1" : "0";
        slide.style.pointerEvents = i === activeIndex ? "all" : "none";
        slide.style.transform = "none";
        slide.style.zIndex = i === activeIndex ? "10" : "0";
      });
      const counter = document.getElementById("slide-counter");
      if (counter) counter.textContent = `${activeIndex + 1} / ${slides.length}`;

      const activeSlide = slides[activeIndex];
      const skipSelector = "script, style, svg, button, #nav-dots, #slide-counter, .nav-dot";
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
      return items;
    }, index);

    const role = await page.evaluate((activeIndex) => {
      const slide = document.querySelectorAll("section.slide")[activeIndex];
      const layoutClass = Array.from(slide.classList).find((name) => name.startsWith("slide--"));
      return layoutClass ? layoutClass.replace(/^slide--/, "").replace(/-/g, "_") : "body";
    }, index);

    await page.screenshot({ path: backgroundPath, fullPage: false });
    slides.push({
      slide: index + 1,
      role,
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
    line: ctx.line("#FFFFFF", 0, "solid"),
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
    alt: "Signal HTML-rendered background ${slideNo}",
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
    "6x3",
    "-geometry",
    "320x180+8+8",
    "-background",
    "#1C2644",
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
        visual_master: "signal",
        render_strategy: "html_background_with_editable_text_overlay",
        viewport: VIEWPORT,
        slide_size: SLIDE,
        classroom_readability: {
          target: "3m classroom projector readability",
          minimum_extracted_font_px: 16,
          base_body_scale: 1.18,
          label_floor_px: 16,
          body_floor_px: 18
        },
        notes: [
          "Background images are rendered from the source HTML template.",
          "Editable text boxes are overlaid from DOM text-node coordinates with transparent text color to avoid double-rendering over the screenshot background.",
          "Browser navigation controls and fixed browser slide counter are hidden; per-slide footer/chrome remains part of the background.",
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
