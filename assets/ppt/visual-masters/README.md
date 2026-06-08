# PPT Visual Master Development Spec

This directory stores visual master assets for Kabuqina's `student-ppt` capability, displayed to users as "生成汇报（PPT）".

The visual master is a Writer resource. It is not a product capability and it is not the report structure. The report structure is chosen first, then the outline is generated, then the user chooses a visual master, and finally `pptx_write` renders the deck.

## Product Flow

1. User selects an entry: course report, paper/literature report, or code/project defense.
2. The entry determines the structure template:
   - `course_report`
   - `paper_report`
   - `code_defense`
3. The agent reads source material and generates a structured outline.
4. The user reviews or edits the outline.
5. The user selects a visual master.
6. The Writer receives `slides`, `structure_template`, and `visual_master`.
7. The Writer generates the final `.pptx`.

## Asset Directory Contract

Each visual master must live in its own kebab-case directory:

```text
assets/
  ppt/
    visual-masters/
      manifest.json
      soft-editorial/
        template.pptx
        preview.png
        metadata.json
```

Required files:

- `template.pptx`: the editable PowerPoint master/sample deck.
- `metadata.json`: machine-readable metadata for discovery and compatibility.

Recommended files:

- `preview.png`: a thumbnail or contact-sheet preview shown in the frontend.

## Naming Rules

- Directory name: kebab-case, for example `soft-editorial`.
- Metadata `id`: snake_case, for example `soft_editorial`.
- Display `name`: short title case, for example `Soft Editorial`.
- Use stable IDs. Do not rename an ID after it is shipped unless a migration is added.

## Required Metadata

Each `metadata.json` should follow this shape:

```json
{
  "id": "soft_editorial",
  "name": "Soft Editorial",
  "description": "Soft editorial presentation master for student course reports, paper presentations, and project defenses.",
  "template_file": "template.pptx",
  "preview_file": "preview.png",
  "status": "candidate",
  "compatible_structures": [
    "course_report",
    "paper_report",
    "code_defense"
  ],
  "layout_hints": [
    "title",
    "section",
    "two_col",
    "three_cards",
    "stats",
    "quote",
    "timeline",
    "matrix",
    "chart",
    "closing"
  ],
  "source_notes": "Brief provenance or authoring notes."
}
```

`status` values:

- `candidate`: asset is present, but not wired into the Writer/frontend yet.
- `available`: asset is wired into discovery, frontend selection, and Writer output.
- `disabled`: asset remains in the repo but is hidden from normal selection.

## Master Deck Requirements

One visual master should be a reusable slide-layout vocabulary, not a fixed 10-page report. A 10-slide sample deck is enough when it covers the required layout roles. Generated PPTs may have more pages by reusing these layout roles.

Required layout roles:

- `title`: cover slide.
- `section`: chapter divider.
- `body`: normal explanation or claim slide.
- `two_col`: comparison, method/detail split, or problem/solution.
- `three_cards`: 3-part summary, method components, or key findings.
- `stats`: key numbers or experiment metrics.
- `quote`: conclusion, insight, or highlighted statement.
- `timeline`: process, roadmap, or experiment flow.
- `matrix`: comparison table or framework grid.
- `chart`: chart/image placeholder with caption.
- `closing`: final thanks or summary page.

Optional layout roles:

- `agenda`
- `qa_backup`
- `code`
- `formula`
- `image_full_bleed`
- `table_dense`

## Slide Count Guidance

Target 10 to 12 slides per master deck:

1. Cover/title.
2. Section divider.
3. Body/claim slide.
4. Two-column slide.
5. Three-card slide.
6. Stats/data highlight.
7. Quote/insight slide.
8. Timeline/process slide.
9. Matrix/table slide.
10. Chart or image placeholder slide.
11. Optional backup/Q&A slide.
12. Closing slide.

It is acceptable to ship 10 slides when the core roles are covered.

## Visual Quality Requirements

Each master should feel distinct but student-friendly:

- Suitable for university course reports, paper presentations, and project defenses.
- Clear at classroom projector distance.
- Professional but not overly corporate.
- Editable in PowerPoint or WPS after generation.
- Uses real PowerPoint text boxes, shapes, lines, tables, and placeholders where possible.
- Avoids relying on large raster backgrounds.
- Avoids logos, copyrighted images, watermarks, and hardcoded personal names.
- Avoids tiny text, dense decorative grids, and pure title-plus-bullet pages.
- Provides enough whitespace for generated content to vary in length.

Recommended minimum type sizes:

- Cover title: 34 pt or larger.
- Slide title: 24 pt or larger.
- Body text: 16 pt or larger.
- Captions/footers: 10 pt or larger.

## Content Placeholder Rules

The sample deck may include realistic dummy student content, but it must be easy to replace.

Use neutral examples such as:

- Course report.
- Literature review.
- Project defense.
- Research method.
- Experiment result.

Do not use:

- Private names, student IDs, phone numbers, email addresses, school IDs, or real unpublished data.
- External images without license notes.
- Decorative assets that cannot be redistributed.

For missing real evidence, use explicit placeholders such as:

- `[ 在此处插入图表 ]`
- `[ 在此处插入实验截图 ]`
- `[ 在此处插入系统架构图 ]`

## Technical Requirements

- File format must be `.pptx`.
- Prefer 16:9 widescreen.
- Keep the file reasonably small. A master with no embedded media is ideal.
- Use one coherent theme and one coherent master when possible.
- Avoid external font dependencies. Prefer fonts normally available on Windows or safe fallbacks.
- All important content must be editable, not flattened into screenshots.
- Each layout should have a clear role that can be mapped from generated slide types.

Current generated slide types that should map cleanly:

- `agenda`
- `claim_bullets`
- `diagram`
- `table`
- `screenshot_placeholder`
- `chart_placeholder`
- `qa_backup`
- `closing`

## Compatibility Expectations

The same visual master should work across the three first structure templates unless metadata says otherwise:

- `course_report`: classroom learning report, chapter summary, course reflection.
- `paper_report`: paper/literature presentation, research summary.
- `code_defense`: course design, code project defense, software demo report.

If a master is only suitable for one structure, restrict `compatible_structures` in `metadata.json`.

## Frontend Selection Expectations

The frontend should eventually show:

- master name,
- preview image,
- short description,
- compatible report structures,
- status if the master is not yet available.

The frontend selection should happen after outline review, because the structure entry should first determine what story is being generated.

## Acceptance Checklist

Before a visual master is marked `available`:

- `template.pptx` opens in PowerPoint or WPS.
- `metadata.json` is valid JSON.
- The master appears in `manifest.json`.
- The ID is stable and unique.
- At least 10 layout roles are covered or intentionally documented.
- The deck has no private information.
- The deck has no unlicensed external images.
- The deck can support more generated slides by reusing layouts.
- The frontend can show the master as a selectable option.
- The Writer can generate a PPTX using this `visual_master`.

## Current Available Masters

- `soft_editorial`
- `blue_professional`
- `signal`
- `neo_grid_bold`
- `editorial_forest`
