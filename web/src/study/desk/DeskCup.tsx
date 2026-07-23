// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type { DeskArtAssets } from "./artAssets";

export interface DeskCupProps {
  art: DeskArtAssets;
  /** Course chat is a future surface; clicking only announces. */
  onAskTutor: () => void;
}

export function DeskCup({ art, onAskTutor }: DeskCupProps) {
  const Coffee = art.coffee;
  return (
    <div className="kd-cup-zone">
      <button type="button" className="kd-cup-button" onClick={onAskTutor}>
        <Coffee />
        <span>碰杯问小娜</span>
      </button>
      <span className="kd-cup-status">安静陪着你</span>
    </div>
  );
}
