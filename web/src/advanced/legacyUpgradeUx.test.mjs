import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const settings = readFileSync(new URL("./settings/SettingsLegacyChannels.tsx", import.meta.url), "utf8");
const routes = readFileSync(new URL("../main.tsx", import.meta.url), "utf8");
const tombstone = readFileSync(new URL("./pages/PlatformRouteGuard.tsx", import.meta.url), "utf8");
const scheduledTasks = readFileSync(new URL("./pages/ScheduledTasks.tsx", import.meta.url), "utf8");

assert.match(settings, /cmd_legacy_channel_inventory/);
assert.match(settings, /cmd_legacy_channel_export/);
assert.match(settings, /cmd_legacy_channel_cleanup/);
assert.match(settings, /confirmation:\s*"REMOVE_LEGACY_CHANNEL_DATA"/);
assert.match(settings, /!exported\s*\|\|\s*exported\.skippedOversizeFiles\.length\s*>\s*0/);
assert.match(routes, /path="\/settings\/feishu"[\s\S]*LegacyPlatformTombstonePage/);
assert.match(routes, /path="\/settings\/wecom"[\s\S]*LegacyPlatformTombstonePage/);
assert.match(tombstone, /did not[\s\S]*redirect this channel to another platform/);
assert.match(scheduledTasks, /job\.deliveryUnavailable[\s\S]*cron\.unsupportedDelivery/);

console.log("legacy upgrade UX contract ok");
