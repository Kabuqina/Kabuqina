// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type { DeskArtAssets } from "./artAssets";

export interface DeskCupProps {
  art: DeskArtAssets;
  onAskTutor: () => void;
}

export function DeskCup({ art, onAskTutor }: DeskCupProps) {
  const Coffee = art.coffee;
  return (
    <div className="kd-cup-zone">
      <button
        id="kd-cup-chat"
        type="button"
        className="kd-cup-button"
        aria-controls="kd-invoke-card"
        onClick={onAskTutor}
      >
        <Coffee />
        <span>碰杯问小娜</span>
      </button>
      <span className="kd-cup-status">安静陪着你</span>
    </div>
  );
}
