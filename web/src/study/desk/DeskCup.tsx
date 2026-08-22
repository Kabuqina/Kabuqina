// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import type { DeskArtAssets } from "./artAssets";
import { ART_ASSETS } from "../../lib/artAssets";

export interface DeskCupProps {
  art: DeskArtAssets;
  onAskTutor: () => void;
}

export function DeskCup({ art: _art, onAskTutor }: DeskCupProps) {
  return (
    <div className="kd-cup-zone">
      <button
        id="kd-cup-chat"
        type="button"
        className="kd-cup-button"
        aria-controls="kd-invoke-card"
        onClick={onAskTutor}
      >
        <img className="kd-cup-button__mascot" src={ART_ASSETS.companionPill} alt="" />
        <span>碰杯问小娜</span>
      </button>
    </div>
  );
}
