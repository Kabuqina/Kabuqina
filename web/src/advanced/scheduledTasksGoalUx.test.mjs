/* global URL */
import assert from "node:assert/strict";
import fs from "node:fs";

const pageSource = fs.readFileSync(
  new URL("./pages/ScheduledTasks.tsx", import.meta.url),
  "utf8",
);
const stringsSource = fs.readFileSync(
  new URL("../locales/strings.ts", import.meta.url),
  "utf8",
);

assert.match(
  pageSource,
  /mode:\s*string \| null[\s\S]*goalStatus:\s*string \| null[\s\S]*goalCostAccounting:\s*string \| null/,
  "Scheduled task types should include the sanitized goal projection.",
);
assert.match(
  pageSource,
  /renderGoalCard[\s\S]*cron\.goalBadge[\s\S]*goalIteration[\s\S]*cron\.goalCost[\s\S]*goalUpdatedAt/,
  "Goal cards should render status, iteration, cost, and update time.",
);
assert.match(pageSource, /job\.goalCostUsd/, "Goal cards should render projected cost.");
assert.match(
  pageSource,
  /goalCostAccounting === "incomplete"[\s\S]*cron\.goalCostUnknown/,
  "Incomplete goal cost accounting must render as unknown rather than zero.",
);

const goalCard = pageSource.match(
  /const renderGoalCard[\s\S]*?\n[ ]{2}const renderActiveCard/,
)?.[0] ?? "";
assert.ok(goalCard, "Scheduled Tasks should define a dedicated goal card.");
assert.doesNotMatch(
  goalCard,
  /<Toggle|handleToggle|cmd_cron_toggle|handleDelete|cmd_cron_delete/,
  "G0 goal cards must stay status-only and expose no legacy controls.",
);
assert.doesNotMatch(
  goalCard,
  /job\.prompt|lastDeliveryError/,
  "Goal cards must not render prompts or error stacks.",
);
assert.match(
  pageSource,
  /job\.mode === "goal"[\s\S]*renderGoalCard\(job\)/,
  "Goal jobs should route to the status-only card.",
);
assert.match(
  pageSource,
  /const renderCompletedCard[\s\S]*job\.mode === "goal"[\s\S]*renderGoalCard\(job\)/,
  "Completed Goal Tasks must remain status-only instead of exposing legacy delete controls.",
);
assert.match(stringsSource, /goalBadge:\s*"持续目标"/);
assert.match(stringsSource, /goalBadge:\s*"Goal Task"/);
assert.match(stringsSource, /goalCostUnknown/);
