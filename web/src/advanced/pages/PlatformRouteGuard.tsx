import type { ReactNode } from "react";
import { Section } from "../../components/ui/Section";
import { useProductProfileContract } from "../../lib/productProfileContract";
import { PlatformPage } from "./PlatformPage";

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
