import { Section } from "../../components/ui/Section";
import { PlatformPage } from "./PlatformPage";
import { Button } from "../../components/ui/Button";
import { useNavigate } from "react-router-dom";

/**
 * Tombstone for every v0.4 Settings channel link. Kept so old deep-links explain
 * the upgrade instead of dead-ending; it is not a configuration surface.
 *
 * As of v0.5.0 (CTL-C08) this covers the mobile Bot channels and email too — the
 * Bot product surface is gone, and `PlatformRouteGuard` / `RetainedPlatformPendingPage`
 * went with it since there is no longer a visible-gateway set to guard against.
 */
export function LegacyPlatformTombstonePage({ platform }: { platform: string }) {
  const nav = useNavigate();
  return (
    <PlatformPage title={`${platform} is no longer available`}>
      <Section title="Historical channel data">
        <div className="space-y-3 text-sm text-[var(--kq-color-muted)]">
          <p>
            This v0.4 Settings link is retained only to explain the upgrade. Kabuqina did not
            redirect this channel to another platform, and old scheduled targets remain visible
            as unsupported delivery records.
          </p>
          <p>Export any historical data before using the explicit cleanup control.</p>
          <Button type="button" variant="secondary" onClick={() => nav("/settings", { state: { settingsTab: "advanced" } })}>
            Open legacy data controls
          </Button>
        </div>
      </Section>
    </PlatformPage>
  );
}
