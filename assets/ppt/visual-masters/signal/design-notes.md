# Signal Rescue Notes

`signal` has been rebuilt from the copied HTML template in `assets\ppt\visual-masters\signal\signal_html`.

The current `template.pptx` is an HTML-background hybrid master. Each slide uses a high-fidelity browser-rendered PNG from the source HTML as the background, then overlays editable PowerPoint text boxes extracted from DOM text-node coordinates. Overlay text is transparent, so the screenshot carries the visual appearance and the text boxes provide selectable/editable structure.

This is intentionally not a pure native-PowerPoint rebuild. The first goal is visual fidelity and a stable Writer-facing interface. A later native rebuild can replace the background screenshots while keeping the same roles in `frame-map.json`.

The build script applies a classroom readability override. It forces animated HTML elements into their final visible state, hides browser navigation dots and the fixed slide counter, enlarges body and label text, and keeps extracted text at or above 16px for projection readability at roughly 3 meters.

## Design Identity

Signal is a sober institutional presentation system:

- deep navy canvas: `#1C2644`;
- bone paper alternate canvas: `#F0ECE3`;
- single muted gold accent: `#C8A870`;
- warm off-white text on dark: `#E2DCD0`;
- editorial serif headlines using Source Serif 4;
- clean sans body using DM Sans;
- mono chrome using IBM Plex Mono;
- subtle navy grid texture and hairline dividers;
- no playful decoration, no glossy gradients, no multi-accent palette.

The style is best for student reports that need to feel credible, academic, and weighty: paper presentations, course defenses, policy/literature reviews, research summaries, and data-heavy project reporting.

It is weaker for playful classroom activities, image-led showcases, highly colorful brand decks, or casual club presentations.

## Source Layout Roles

The HTML template defines these reusable slide classes:

| Source layout | Product role | Writer mapping |
| --- | --- | --- |
| `slide--cover` | `cover` | cover/title slide |
| `slide--chapter` | `chapter` | section divider |
| `slide--statement` | `statement` | thesis/claim/transition |
| `slide--split` | `split` | two-column explanation |
| `slide--stats` | `stats` | metric summary |
| `slide--quote` | `quote` | major insight or quotation |
| `slide--list` | `list` | agenda/principles/recommendations |
| `slide--compare` | `compare` | before/after or contrast |
| `slide--editorial` | `editorial` | dense evidence/case-study page |
| `slide--dense` | `dense` | long-form two-column analysis |
| `slide--end` | `closing` | final contact or conclusion |
| `slide--chart` | `chart` | chart placeholder/bar chart |
| `slide--diagram` | `diagram` | four-step process |
| `slide--pie` | `pie` | donut/pie breakdown |
| `slide--pyramid` | `pyramid` | hierarchy/framework |
| `slide--vtimeline` | `vtimeline` | vertical timeline |
| `slide--cycle` | `cycle` | operating cycle |

These roles are captured in `frame-map.json`.

## Rebuild Requirements

If this master is later rebuilt as a true native PowerPoint template, the rebuild should:

1. Create real named layouts or a writer-native renderer for every role in `frame-map.json`.
2. Use a stable prefix such as `SIG_COVER`, `SIG_CHAPTER`, `SIG_STATEMENT`, `SIG_SPLIT`, `SIG_STATS`, `SIG_QUOTE`, `SIG_LIST`, `SIG_COMPARE`, `SIG_EDITORIAL`, `SIG_DENSE`, `SIG_CLOSING`, `SIG_CHART`, `SIG_DIAGRAM`, `SIG_PIE`, `SIG_PYRAMID`, `SIG_VTIMELINE`, and `SIG_CYCLE`.
3. Preserve the deep navy plus bone paper system.
4. Keep muted gold as the only accent color.
5. Preserve serif headline dominance and mono chrome.
6. Keep content-safe regions generous enough for generated Chinese text.
7. Avoid sample organizations, private names, and hardcoded real sources.

## Current Status

Status remains `candidate` until the frontend and Writer consume `visual_master=signal`.

The asset now has:

- `template.pptx`: HTML-background hybrid PPTX;
- `backgrounds/`: one browser-rendered PNG background per slide;
- `text-layer.json`: DOM-derived editable text box coordinates;
- `preview.png`: 18-slide contact sheet;
- `metadata.json`: product metadata and design tokens;
- `frame-map.json`: interface contract between Writer slide types and source visual frames;
- `design-notes.md`: rebuild and review guidance.
