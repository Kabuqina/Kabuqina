// Copyright 2026 Kabuqina Contributors
// SPDX-License-Identifier: Apache-2.0

import { CompanionCupSvg } from "./CompanionCupSvg";
import { KabuqinaCoasterSvg } from "./KabuqinaCoasterSvg";
import { KabuqinaSceneSvg } from "./KabuqinaSceneSvg";

const previewCardClass =
  "rounded-xl border border-[rgba(184,169,201,0.34)] bg-white/78 p-5 shadow-[0_8px_24px_rgba(90,74,106,0.08)]";

export function BrandSvgPreview() {
  return (
    <main className="h-full overflow-y-auto bg-[linear-gradient(135deg,#f3edf6_0%,#fbf8fb_44%,#fffafa_100%)] px-6 py-8 text-[var(--kq-color-ink)]">
      <div className="mx-auto flex max-w-6xl flex-col gap-6">
        <header className="flex flex-col gap-2">
          <p className="text-sm font-medium text-[var(--kq-color-muted)]">Kabuqina SVG component preview</p>
          <h1 className="text-3xl font-semibold tracking-normal">Canonical brand SVGs</h1>
        </header>

        <section className="grid gap-4 md:grid-cols-3">
          <div className={previewCardClass}>
            <p className="mb-4 text-sm font-medium text-[var(--kq-color-muted)]">Mascot cup, no steam</p>
            <div className="grid place-items-center rounded-lg bg-[rgba(250,246,255,0.72)] p-7">
              <CompanionCupSvg className="h-44 w-44" decorative={false} title="Kabuqina companion cup" />
            </div>
          </div>
          <div className={previewCardClass}>
            <p className="mb-4 text-sm font-medium text-[var(--kq-color-muted)]">Mascot cup, steam on</p>
            <div className="grid place-items-center rounded-lg bg-[rgba(250,246,255,0.72)] p-7">
              <CompanionCupSvg className="h-44 w-44" steam decorative={false} title="Kabuqina companion cup with steam" />
            </div>
          </div>
          <div className={previewCardClass}>
            <p className="mb-4 text-sm font-medium text-[var(--kq-color-muted)]">Coaster asset</p>
            <div className="grid place-items-center rounded-lg bg-[rgba(250,246,255,0.72)] p-7">
              <KabuqinaCoasterSvg className="w-56" variant="pill" decorative={false} title="Kabuqina gingham coaster" />
            </div>
          </div>
        </section>

        <section className={previewCardClass}>
          <p className="mb-4 text-sm font-medium text-[var(--kq-color-muted)]">Frontend combined default</p>
          <div className="grid min-h-80 place-items-center rounded-lg bg-[rgba(255,255,255,0.54)] p-5">
            <KabuqinaSceneSvg variant="pill" className="w-full max-w-sm" decorative={false} title="Kabuqina cup on coaster" />
          </div>
        </section>

        <section className={previewCardClass}>
          <p className="mb-4 text-sm font-medium text-[var(--kq-color-muted)]">Three frontend replacement targets</p>
          <div className="grid gap-5 lg:grid-cols-[0.8fr_1.2fr_0.7fr]">
            <div className="rounded-lg bg-[rgba(250,246,255,0.72)] p-5">
              <p className="mb-3 text-sm font-medium text-[var(--kq-color-muted)]">1. Pill mascot</p>
              <div className="grid h-40 place-items-center">
                <KabuqinaSceneSvg variant="pill" className="w-28" decorative={false} title="Preview pill mascot replacement" />
              </div>
            </div>
            <div className="rounded-lg bg-[rgba(255,255,255,0.68)] p-5">
              <p className="mb-3 text-sm font-medium text-[var(--kq-color-muted)]">2. Empty chat hero</p>
              <div className="grid h-56 place-items-center">
                <KabuqinaSceneSvg
                  variant="hero"
                  className="w-[7.75rem]"
                  decorative={false}
                  title="Preview empty chat hero replacement"
                />
              </div>
            </div>
            <div className="rounded-lg bg-[rgba(250,246,255,0.72)] p-5">
              <p className="mb-3 text-sm font-medium text-[var(--kq-color-muted)]">3. Chat avatar</p>
              <div className="grid h-40 place-items-center">
                <div className="grid h-[2.875rem] w-[2.875rem] place-items-center">
                  <CompanionCupSvg className="h-full w-full drop-shadow-[0_1px_4px_rgba(90,74,106,0.12)]" decorative={false} title="Preview chat avatar replacement" />
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="grid gap-4 lg:grid-cols-3">
          <div className={previewCardClass}>
            <p className="mb-4 text-sm font-medium text-[var(--kq-color-muted)]">Hero scene</p>
            <div className="grid min-h-64 place-items-center rounded-lg bg-[rgba(255,255,255,0.54)] p-4">
              <KabuqinaSceneSvg variant="hero" className="w-full max-w-sm" decorative={false} title="Kabuqina hero scene" />
            </div>
          </div>
          <div className={previewCardClass}>
            <p className="mb-4 text-sm font-medium text-[var(--kq-color-muted)]">Pill scene</p>
            <div className="grid min-h-64 place-items-center rounded-lg bg-[rgba(255,255,255,0.54)] p-4">
              <KabuqinaSceneSvg variant="pill" className="w-full max-w-xs" decorative={false} title="Kabuqina pill scene" />
            </div>
          </div>
          <div className={previewCardClass}>
            <p className="mb-4 text-sm font-medium text-[var(--kq-color-muted)]">Social scene</p>
            <div className="grid min-h-64 place-items-center rounded-lg bg-[rgba(255,255,255,0.54)] p-4">
              <KabuqinaSceneSvg
                variant="social"
                className="w-full max-w-sm"
                decorative={false}
                title="Kabuqina social preview scene"
              />
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
