# Neo Grid Bold Rescue Notes

`neo_grid_bold` has been rebuilt from `assets\ppt\visual-masters\neo-grid-bold\neo-grid-bold_html`.

The current `template.pptx` is an HTML-background hybrid master. Each slide uses a browser-rendered PNG background from the source HTML, with transparent editable PowerPoint text boxes overlaid from DOM text-node coordinates.

The build script uses the deck-stage API to activate each slide, hides deck-stage navigation chrome before capture, applies a classroom readability floor, and rewrites text-box outlines to DrawingML `noFill` for LibreOffice and WPS compatibility.

## Design Identity

Neo Grid Bold is a graphic, design-led presentation system:

- off-white canvas: `#ECECE8`;
- paper cards: `#F5F4EF`;
- ink black: `#0A0A0A`;
- single neon-yellow accent: `#E6FF3D`;
- Space Grotesk for display and body;
- JetBrains Mono for labels and technical chrome;
- hard grid structure, black blocks, bright emphasis, no soft decoration.

It is strongest for student product defenses, design reviews, code/project demos, entrepreneurship pitches, and high-energy research summaries.

It is weaker for quiet academic literature reports, traditional thesis defenses, or any topic that needs warmth and restraint.

## Source Layout Roles

| Source layout | Product role | Writer mapping |
| --- | --- | --- |
| `s-cover` | `cover` | cover/title |
| `s-toc` | `toc` | agenda/contents |
| `s-stats` | `stats` | metric summary |
| `s-features` | `features` | three cards/features |
| `s-chart` | `chart` | bar chart |
| `s-section` | `section` | section divider |
| `s-quote` | `quote` | quote/insight |
| `s-cta` | `cta` | next steps |
| `s-consult` | `consult` | dense finding page |
| `s-chart2` | `chart2` | line chart/cohort curve |
| `s-process2` | `process2` | process/roadmap |
| `s-matrix2` | `matrix2` | comparison matrix |

The copied HTML contains 12 sections. `template.json` lists 13 slides, but the generated master follows the actual source HTML.

## Current Status

Status remains `candidate` until the frontend and Writer consume `visual_master=neo_grid_bold`.
