import type { ReactNode } from "react";
import { Section } from "../../components/ui/Section";
import { useProductProfileContract } from "../../lib/productProfileContract";
import { PlatformPage } from "./PlatformPage";
import { Button } from "../../components/ui/Button";
import { useNavigate } from "react-router-dom";

export function PlatformRouteGuard({ platform, children }: { platform: string; children: ReactNode }) {
  const contract = useProductProfileContract();
  if (contract.visibleGateways.includes(platform)) return <>{children}</>;
  return (
    <PlatformPage title="Channel unavailable">
      <Section title="Product profile boundary">
        <p className="text-sm text-[var(--kq-color-muted)]">
          This channel is not available in the active product profile ({contract.profile}).
          No configuration or gateway state was created.
        </p>
      </Section>
    </PlatformPage>
  );
}

export function RetainedPlatformPendingPage({ platform }: { platform: string }) {
  return (
    <PlatformPage title={platform}>
      <Section title="Retained channel">
        <p className="text-sm text-[var(--kq-color-muted)]">
          This channel is retained by the product profile. Its configuration workflow is owned by a later readiness gate.
        </p>
      </Section>
    </PlatformPage>
  );
}

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
