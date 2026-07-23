// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type { DeskArtAssets } from "./artAssets";

export interface DeskChromeProps {
  art: DeskArtAssets;
  onFutureFeature: () => void;
  onOpenChat?: () => void;
  onOpenActivity?: () => void;
  onOpenSettings?: () => void;
}

export function DeskChrome({
  art,
  onFutureFeature,
  onOpenChat,
  onOpenActivity,
  onOpenSettings,
}: DeskChromeProps) {
  const SettingsIcon = art.settings;
  return (
    <header className="kd-product-chrome">
      <div className="kd-brand">
        <span className="kd-brand-mark" aria-hidden="true">K</span>
        <strong className="kd-brand-copy">Kabuqina</strong>
      </div>
      <nav className="kd-top-nav" aria-label="一级目的地">
        <button type="button" aria-current="page">学习</button>
        <button type="button" aria-current="false" onClick={onOpenChat ?? onFutureFeature}>对话</button>
      </nav>
      <div className="kd-utilities">
        <button type="button" className="kd-hide-narrow" onClick={onOpenActivity ?? onFutureFeature}>Activity</button>
        <button type="button" aria-label="设置" onClick={onOpenSettings ?? onFutureFeature}>
          <SettingsIcon />
        </button>
      </div>
    </header>
  );
}
