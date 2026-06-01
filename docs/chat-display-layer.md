# Chat Display Layer

> Status: **In progress**  
> Last updated: 2026-05-31

Kabuqina's file-generation pipeline is:

```text
Read Layer
  -> Material Index
    -> Planner
      -> Writer
```

That pipeline explains how source files become generated deliverables such as
PPTX, reports, notes, or spreadsheets. It does **not** fully describe what
happens when the agent answers in chat.

Chat display is a separate product surface:

```text
Read Layer / Agent Output
  -> Chat Display Layer
```

A related but distinct surface is learning interaction:

```text
Read Layer / Agent Output / Student State
  -> Chat Display Layer
    -> Learning Interaction Layer
```

Chat Display renders the answer; the Learning Layer decides whether the answer
should be an explanation, hint, quiz, derivation, formula-code bridge, or other
student-facing learning behavior. See `docs/learning-layer.md`.

The Chat Display Layer turns agent output and Read-layer results into a clear,
inspectable, interactive conversation view. It is not the Writer layer because it
does not render a final file; it renders the live workspace where the user reads,
checks, copies, and follows up.

## Why This Layer Exists

Students do not only ask Kabuqina to generate files. They also ask it to:

- read a paper and explain it;
- show extracted formulas;
- compare equations;
- turn formulas into code;
- turn code into formulas;
- inspect tables and citations before using them in a report;
- verify whether OCR or parser output is reliable;
- continue discussing a source file without generating a PPT or Word document.

Those workflows need high-quality display even when no file is produced.

Without a Chat Display Layer, Read improvements may only produce better raw
Markdown while the user still sees hard-to-read formula source, broken tables, or
unclear parser warnings.

## Boundary With Writer

| Layer | Output target | Main job |
|-------|---------------|----------|
| Writer | Files such as `.pptx`, `.docx`, `.pdf`, `.xlsx` | Produce editable/deliverable artifacts |
| Chat Display Layer | Chat UI | Render live answers and extracted material clearly |

The same Read result may feed both:

- Writer uses it to generate final documents.
- Chat Display uses it to show readable previews, citations, formulas, warnings,
  and copyable snippets.

Writer should not own chat rendering rules. Chat Display should not own final
file layout rules.

## Responsibilities

The Chat Display Layer owns:

- Markdown rendering.
- LaTeX math rendering for inline `$...$` and block `$$...$$` formulas.
- Code block rendering and syntax highlighting.
- Tables, lists, headings, and blockquotes.
- Source references such as file names, page numbers, slide numbers, or
  `read_id`-derived provenance.
- Attachment and image previews.
- Tool progress and long-running turn status.
- Parser warnings and uncertainty display.
- Copy affordances for formulas, code blocks, tables, citations, and source
  snippets.
- Accessibility of rendered content in the chat surface.

## Non-Responsibilities

The Chat Display Layer does not:

- read files directly;
- OCR images or PDFs;
- build Material Index;
- decide a PPT/report/story structure;
- generate final files;
- repair uncertain extracted facts with an LLM;
- hide parser uncertainty to make an answer look polished.

If formula extraction is wrong, the fix belongs in the Read layer. If a formula
is extracted correctly but displayed as raw text, the fix belongs in Chat
Display.

## Formula Handling

Formula support has two separate requirements:

1. **Read Layer extraction**
   `document_read_precise` / `pdf_read_precise` with `mode=math` asks Docling to
   perform formula enrichment and return LaTeX-oriented output where possible.

2. **Chat Display rendering**
   The frontend must render LaTeX syntax into readable formulas. Markdown can
   carry formulas as text:

   ```md
   Inline formula: $E = mc^2$

   Block formula:

   $$\int_a^b f(x)\,dx$$
   ```

   But the chat UI needs a math renderer such as KaTeX or MathJax to display
   those as formulas instead of raw source.

Good formula UX should include:

- rendered formula view;
- copy LaTeX source;
- fallback to raw source if rendering fails;
- visible warning when the Read layer marks formula OCR as uncertain;
- preservation of surrounding explanatory text and page/source reference.

## Suggested Frontend Shape

Current likely home:

- `web/src/chat/ChatMarkdown.tsx`
- `web/src/chat/ChatMessageList.tsx`

Expected additions:

- Markdown math plugin support, for example `remark-math`.
- Renderer support, for example `rehype-katex` plus KaTeX CSS, or MathJax if
  runtime rendering is preferred.
- Styling that fits compact chat messages and works in dark/light themes.
- Copy controls for block formulas without cluttering ordinary prose.
- Graceful rendering error fallback.

## Source References and Uncertainty

Read results should preserve metadata such as:

- source file name;
- path or workspace-relative path;
- page/slide/sheet;
- parser engine;
- `read_id`;
- warnings and uncertainty.

Chat Display should make this visible when useful, especially for student
workflow trust:

- "Formula extracted from page 4";
- "Used text-only fallback";
- "OCR/formula extraction may be uncertain";
- "Source: `paper.pdf`, Docling math mode".

This matters because the chat answer is often where the user decides whether to
trust the extracted material before asking for a generated deliverable.

## Relationship to Material Index

Material Index remains the deterministic evidence bridge for generated files.
Chat Display may show Material Index results, but it is not required for every
chat answer.

Examples:

- User asks "show me all equations from this paper" → Read Layer + Chat Display
  may be enough.
- User asks "make a PPT from this paper" → Read Layer + Material Index + Planner
  + Writer, with Chat Display showing progress and outline review.
- User asks "explain equation 3 and turn it into Python" → Read Layer extracts
  formula, Chat Display renders it, the agent explains and may provide code.

## Implementation Phases

### Phase 1: Math Rendering

- Add frontend support for inline and block LaTeX rendering.
- Ensure `$...$` and `$$...$$` survive Markdown processing.
- Add copy affordance for block formulas.
- Add tests or rendering checks for light/dark themes.

Current implementation:

- `web/src/chat/ChatMarkdown.tsx` renders inline/block math through
  `remark-math` + `rehype-katex`.
- Block formulas expose a "Copy LaTeX" control that copies the original
  KaTeX `application/x-tex` source when available.
- Code blocks have syntax highlighting and per-block copy controls.
- GitHub-style callouts such as `> [!WARNING]` and `> [!SOURCE]` render as
  compact chat cards, giving the Read layer and agent a Markdown-native way to
  surface parser warnings and source references before a structured protocol is
  added.

### Phase 2: Source and Warning UI

- Render parser warnings and uncertainty in a consistent compact style.
- Show source/page references when Read-layer output includes them.
- Avoid burying warnings inside raw JSON.

### Phase 3: Structured Read Artifacts

When Read results grow structured fields such as `formulas[]`, `tables[]`, or
`figures[]`, add dedicated chat components for them:

- formula cards;
- table preview with copy/export;
- figure/screenshot previews;
- citation/source chips.

### Phase 4: Learning-Oriented Interactions

For student workflows, add controls that support learning:

- "copy LaTeX";
- "explain this formula";
- "convert to Python";
- "show derivation";
- "compare with code";
- "use this in report/PPT".

These should call existing agent/tool flows rather than putting reasoning logic
inside the display component.

## Testing Expectations

Chat Display changes should be tested separately from Read/Writer tests.

Important cases:

- inline math renders without breaking normal dollar amounts when possible;
- block math renders and remains copyable as LaTeX;
- rendering failure falls back to readable source;
- tables and code blocks still render after math plugins are added;
- dark/light theme styles remain legible;
- long messages do not overflow chat bubbles;
- warnings/source references are visible but not noisy.

## Design Rule

If the feature changes how source material is parsed, it belongs in the Read
Layer.

If the feature changes what facts are selected for a deliverable, it belongs in
Material Index or Planner.

If the feature changes the final generated file, it belongs in Writer.

If the feature changes how an answer or extracted material appears in chat, it
belongs in the Chat Display Layer.
