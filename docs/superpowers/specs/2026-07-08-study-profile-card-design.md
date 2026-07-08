# Study Profile Card Design

## Goal

Replace the always-visible STUDY learning-planning form with a compact, pinned "学习档案" summary card above "构建学习画像".

## Design

- The STUDY right rail shows a small learning profile card at the top of the learning section.
- The card summarizes the highest-signal saved fields: course, goal, profile summary, and current stage.
- If no saved context exists, the card shows a quiet empty hint that the user can build a profile or edit manually.
- The full 12-field study context editor remains available through an edit button on the card.
- Existing learning actions keep their order. "构建学习画像" stays immediately below the card.

## Data Flow

- `StudySection` continues to load/save/clear `StudyContext` through `studyStore`.
- Clicking a learning action still saves the latest context and prepends it to the action prompt.
- The edit modal reuses the existing field definitions and save failure status.

## Testing

- Add source-level chat UX assertions that the profile card appears before the learning actions.
- Assert the full field list is behind a `ShellModal` editor, not the default rail surface.
- Assert zh/en locale keys exist for the new card and edit labels.
