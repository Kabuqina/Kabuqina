/* global URL */
import assert from "node:assert/strict";
import fs from "node:fs";

const markdownSource = fs.readFileSync(new URL("./ChatMarkdown.tsx", import.meta.url), "utf8");
const cssSource = fs.readFileSync(new URL("../index.css", import.meta.url), "utf8");
const packageJson = JSON.parse(fs.readFileSync(new URL("../../package.json", import.meta.url), "utf8"));

assert.match(markdownSource, /import\s+remarkMath\s+from\s+["']remark-math["']/);
assert.match(markdownSource, /import\s+rehypeKatex\s+from\s+["']rehype-katex["']/);
assert.match(markdownSource, /katex\/dist\/katex\.min\.css/);

assert.match(markdownSource, /remarkPlugins=\{\[remarkGfm,\s*remarkMath\]\}/);
assert.match(markdownSource, /rehypePlugins=\{\[/);
assert.match(markdownSource, /rehypeHighlight/);
assert.match(markdownSource, /rehypeKatex/);
assert.match(markdownSource, /function\s+CodeBlock/);
assert.match(markdownSource, /navigator\.clipboard\?\.writeText/);
assert.match(markdownSource, /aria-label=\{done\s+\?\s+t\("chat\.copied"\)\s+:\s+t\("chat\.copy"\)\}/);
assert.match(markdownSource, /<Copy\s+className=/);
assert.match(markdownSource, /function\s+MarkdownCallout/);
assert.match(markdownSource, /READ_CALLOUTS/);
assert.match(markdownSource, /\[!SOURCE\]/);
assert.match(markdownSource, /\[!WARNING\]/);
assert.match(markdownSource, /parseMarkdownCallout/);
assert.match(markdownSource, /function\s+rehypeMathCopy/);
assert.match(markdownSource, /data-kq-copy-tex/);
assert.match(markdownSource, /findMathTex/);
assert.match(markdownSource, /closest\("\[data-kq-copy-tex\]"\)/);
assert.match(markdownSource, /chat\.copyLatex/);
assert.match(markdownSource, /chat\.copiedLatex/);

assert.equal(packageJson.dependencies["remark-math"] !== undefined, true);
assert.equal(packageJson.dependencies["rehype-katex"] !== undefined, true);
assert.equal(packageJson.dependencies.katex !== undefined, true);

assert.match(cssSource, /\.chat-md\s+\.katex-display/);
assert.match(cssSource, /overflow-x:\s*auto/);
assert.match(cssSource, /\.chat-md\s+\.kq-math-copy-card/);
assert.match(cssSource, /\.chat-md\s+\.kq-math-copy-button/);
