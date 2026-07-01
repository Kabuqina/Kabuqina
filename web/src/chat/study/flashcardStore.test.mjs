import assert from "node:assert/strict";
import fs from "node:fs";
import ts from "typescript";

async function importTs(path) {
  const source = fs.readFileSync(new URL(path, import.meta.url), "utf8");
  const js = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ES2022,
      target: ts.ScriptTarget.ES2022,
      jsx: ts.JsxEmit.ReactJSX,
    },
  }).outputText;
  const url = `data:text/javascript;base64,${Buffer.from(js).toString("base64")}`;
  return import(url);
}

function createStorage() {
  const data = new Map();
  return {
    getItem(key) {
      return data.has(key) ? data.get(key) : null;
    },
    setItem(key, value) {
      data.set(key, String(value));
    },
    removeItem(key) {
      data.delete(key);
    },
  };
}

const store = await importTs("./flashcardStore.ts");

const T0 = Date.parse("2026-01-01T00:00:00.000Z");
const DAY = 86_400_000;

// ---------------------------------------------------------------------------
// normalizeCard: validation + sanitization
// ---------------------------------------------------------------------------

assert.equal(store.normalizeCard(null), null);
assert.equal(store.normalizeCard(42), null);
assert.equal(store.normalizeCard({ front: "only front" }), null, "missing back is dropped");
assert.equal(store.normalizeCard({ back: "only back" }), null, "missing front is dropped");
assert.equal(store.normalizeCard({ front: "   ", back: "x" }), null, "blank front is dropped");

const card = store.normalizeCard(
  {
    front: "  What is overfitting?  ",
    back: "Model fits noise in training data.",
    hint: "generalization",
    tags: ["ML", "ml", " Basics ", "", 5, "ML"],
  },
  T0,
);
assert.equal(card.front, "What is overfitting?", "front trimmed");
assert.deepEqual(card.tags, ["ML", "Basics"], "tags deduped case-insensitively, blanks/non-strings dropped");
assert.equal(card.ease, store.DEFAULT_EASE);
assert.equal(card.repetitions, 0);
assert.equal(card.intervalDays, 0);
assert.equal(typeof card.id, "string");
assert.ok(card.id.length > 0 && card.id.length <= 64);

// Field-length caps and control-char stripping.
// Build the dirty input with explicit control-char codepoints (NUL + BEL)
// so the source stays plain text while still exercising the stripper.
const dirtyBack = "b" + String.fromCharCode(0) + String.fromCharCode(7) + "c	d";
const longCard = store.normalizeCard({ front: "a".repeat(5000), back: dirtyBack });
assert.equal(longCard.front.length, store.FLASHCARD_TEXT_LIMIT, "front length-capped");
assert.equal(longCard.back, "bc\td", "C0 control chars stripped, tab kept");

// Tag count cap.
const manyTags = store.normalizeCard({
  front: "f",
  back: "b",
  tags: Array.from({ length: 50 }, (_, i) => `t${i}`),
});
assert.equal(manyTags.tags.length, store.FLASHCARD_MAX_TAGS, "tag count capped");

// Numeric fields coerced and clamped against garbage.
const garbageNums = store.normalizeCard({
  front: "f",
  back: "b",
  ease: "not-a-number",
  repetitions: -5,
  intervalDays: 999999,
  lapses: 1.9,
});
assert.equal(garbageNums.ease, store.DEFAULT_EASE, "bad ease falls back to default");
assert.equal(garbageNums.repetitions, 0, "negative reps clamped to 0");
assert.equal(garbageNums.intervalDays, store.FLASHCARD_MAX_INTERVAL_DAYS, "interval clamped to max");
assert.equal(garbageNums.lapses, 1, "lapses floored");

// oversized id truncated.
const bigId = store.normalizeCard({ id: "x".repeat(200), front: "f", back: "b" });
assert.equal(bigId.id.length, 64);

// ---------------------------------------------------------------------------
// reviewCard: SM-2 variant scheduling (deterministic)
// ---------------------------------------------------------------------------

const fresh = store.normalizeCard({ front: "f", back: "b" }, T0);

// again on a fresh card: interval 1d, lapse recorded, ease down 0.20.
const again = store.reviewCard(fresh, "again", T0);
assert.equal(again.intervalDays, 1);
assert.equal(again.repetitions, 0);
assert.equal(again.lapses, 1);
assert.equal(again.ease, 2.3, "again lowers ease by 0.20");
assert.equal(Date.parse(again.dueAt), T0 + 1 * DAY);

// good graduation ladder: 2d -> 6d -> round(prev*ease).
const g1 = store.reviewCard(fresh, "good", T0);
assert.equal(g1.repetitions, 1);
assert.equal(g1.intervalDays, 2);
assert.equal(g1.ease, 2.5, "good leaves ease unchanged");
const g2 = store.reviewCard(g1, "good", T0);
assert.equal(g2.repetitions, 2);
assert.equal(g2.intervalDays, 6);
const g3 = store.reviewCard(g2, "good", T0);
assert.equal(g3.repetitions, 3);
assert.equal(g3.intervalDays, Math.round(6 * 2.5), "later interval = round(prev*ease) = 15");

// easy first-success gives a longer interval and raises ease.
const e1 = store.reviewCard(fresh, "easy", T0);
assert.equal(e1.intervalDays, 4);
assert.equal(e1.ease, 2.65);

// hard first-success stays short and lowers ease.
const h1 = store.reviewCard(fresh, "hard", T0);
assert.equal(h1.intervalDays, 1);
assert.equal(h1.ease, 2.35);

// Ease never drops below the floor no matter how many lapses.
let sunk = fresh;
for (let i = 0; i < 20; i += 1) sunk = store.reviewCard(sunk, "again", T0);
assert.equal(sunk.ease, store.MIN_EASE, "ease clamped at floor");

// Interval never exceeds the cap even after many easy reviews.
let grown = fresh;
for (let i = 0; i < 40; i += 1) grown = store.reviewCard(grown, "easy", T0 + i * DAY);
assert.ok(grown.intervalDays <= store.FLASHCARD_MAX_INTERVAL_DAYS, "interval capped");

// Unknown grade is treated conservatively as "again" (never silently promotes).
const bogus = store.reviewCard(g2, "teleport", T0);
assert.equal(bogus.intervalDays, 1);
assert.equal(bogus.repetitions, 0);

// ---------------------------------------------------------------------------
// dueCards / deckStats
// ---------------------------------------------------------------------------

const deck = store.normalizeDeck(
  {
    cards: [
      { front: "new", back: "b" }, // fresh, due immediately
      { front: "future", back: "b", repetitions: 3, intervalDays: 10, dueAt: new Date(T0 + 5 * DAY).toISOString(), lastReviewedAt: new Date(T0).toISOString() },
      { front: "overdue", back: "b", repetitions: 2, intervalDays: 3, dueAt: new Date(T0 - DAY).toISOString(), lastReviewedAt: new Date(T0 - 4 * DAY).toISOString() },
      { front: "mature", back: "b", repetitions: 8, intervalDays: 40, dueAt: new Date(T0 + 30 * DAY).toISOString(), lastReviewedAt: new Date(T0).toISOString() },
    ],
  },
  T0,
);
const due = store.dueCards(deck, T0);
assert.deepEqual(due.map((c) => c.front), ["new", "overdue"], "only due cards, fresh first");

const stats = store.deckStats(deck, T0);
assert.equal(stats.total, 4);
assert.equal(stats.due, 2);
assert.equal(stats.fresh, 1);
assert.equal(stats.mature, 1);
assert.equal(stats.learning, 2);

// ---------------------------------------------------------------------------
// upsertCards: dedupe + cap + progress preservation
// ---------------------------------------------------------------------------

const base = store.normalizeDeck({ cards: [{ front: "Keep", back: "old", repetitions: 5, intervalDays: 30 }] }, T0);
const merged = store.upsertCards(
  base,
  [
    store.normalizeCard({ front: " keep ", back: "new dup" }), // duplicate front (case/space) -> skipped
    store.normalizeCard({ front: "Add", back: "added" }),
  ],
  T0,
);
assert.equal(merged.cards.length, 2, "duplicate front not added");
assert.equal(merged.cards[0].repetitions, 5, "existing progress preserved");

// Cap enforced.
const bulk = Array.from({ length: store.FLASHCARD_MAX_CARDS + 50 }, (_, i) => ({ front: `c${i}`, back: "b" }));
const capped = store.upsertCards(store.emptyDeck(), bulk, T0);
assert.equal(capped.cards.length, store.FLASHCARD_MAX_CARDS, "deck capped at max");

// ---------------------------------------------------------------------------
// parseFlashcards: tolerant parsing of untrusted text
// ---------------------------------------------------------------------------

assert.deepEqual(store.parseFlashcards(""), []);
assert.deepEqual(store.parseFlashcards(null), []);
assert.deepEqual(store.parseFlashcards("not json at all"), []);
assert.deepEqual(store.parseFlashcards("{bad json"), []);

const fenced = store.parseFlashcards(
  'Here are your cards:\n```json\n[{"front":"Q1","back":"A1"},{"front":"","back":"skip"},{"front":"Q2","back":"A2","tags":["t"]}]\n```\nGood luck!',
);
assert.equal(fenced.length, 2, "invalid card dropped, valid ones kept from fenced block");
assert.deepEqual(fenced.map((c) => c.front), ["Q1", "Q2"]);

// object-with-cards form and bare array without fences.
assert.equal(store.parseFlashcards('{"cards":[{"front":"a","back":"b"}]}').length, 1);
assert.equal(store.parseFlashcards('[{"front":"a","back":"b"}]').length, 1);

// import cap.
const hugeText = JSON.stringify(Array.from({ length: 500 }, (_, i) => ({ front: `q${i}`, back: "a" })));
assert.equal(store.parseFlashcards(hugeText).length, store.FLASHCARD_MAX_IMPORT, "import capped");

// A JSON string that isn't cards yields [].
assert.deepEqual(store.parseFlashcards('"just a string"'), []);
assert.deepEqual(store.parseFlashcards("[1,2,3]"), [], "non-object array items dropped");

// ---------------------------------------------------------------------------
// normalizeDeck: corrupt-storage resilience
// ---------------------------------------------------------------------------

assert.deepEqual(store.normalizeDeck(null), store.emptyDeck());
assert.deepEqual(store.normalizeDeck("garbage"), store.emptyDeck());
assert.deepEqual(store.normalizeDeck({ cards: "nope" }), store.emptyDeck());
// duplicate ids get regenerated so they never collide.
const dupIds = store.normalizeDeck({
  cards: [
    { id: "same", front: "a", back: "b" },
    { id: "same", front: "c", back: "d" },
  ],
});
assert.notEqual(dupIds.cards[0].id, dupIds.cards[1].id, "duplicate ids regenerated");

// ---------------------------------------------------------------------------
// Persistence (guarded)
// ---------------------------------------------------------------------------

globalThis.window = { localStorage: createStorage(), dispatchEvent() {} };
globalThis.Event = class {
  constructor(type) {
    this.type = type;
  }
};

const savedDeck = store.saveDeck(store.normalizeDeck({ cards: [{ front: "persist", back: "me" }] }, T0));
assert.equal(savedDeck.cards.length, 1);
assert.deepEqual(store.loadDeck().cards.map((c) => c.front), ["persist"]);
assert.deepEqual(store.clearDeck(), store.emptyDeck());
assert.deepEqual(store.loadDeck(), store.emptyDeck());

// Corrupt stored JSON degrades to an empty deck instead of throwing.
window.localStorage.setItem(store.FLASHCARD_STORAGE_KEY, "{bad json");
assert.deepEqual(store.loadDeck(), store.emptyDeck());

console.log("flashcardStore.test.mjs: ok");
