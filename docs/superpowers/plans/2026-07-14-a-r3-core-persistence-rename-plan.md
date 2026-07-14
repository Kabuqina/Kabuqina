# A-R3 Implementation Plan — Core identifiers and persistence migration

**Goal:** Make Kabuqina the canonical runtime/package/persistence identity while
preserving one release of explicit read-old compatibility and never losing an
existing home directory, session database, learning database, or API key.

**Gate:** C track is closed. Commit `f034ac7a` removed the legacy conversation
loop and `HERMES_AGENT_ENGINE`; commit `5613d688` records the C-track close.

## Compatibility audit

| Surface | Current state / risk | A-R3 contract |
|---|---|---|
| Core CLI package | `hermes_cli` is the primary import package | Move implementation to `kabuqina_cli`; keep `hermes_cli` as a deprecated one-release import shim |
| Core modules | `hermes_constants`, `hermes_state`, `hermes_logging`, and `hermes_time` are primary modules | Canonical `kabuqina_*` modules; old modules re-export canonical symbols for one release |
| Python distribution / commands | project `hermes-agent`; `hermes-agent` / `hermes-acp` commands | project `kabuqina-agent`; canonical `kabuqina` / `kabuqina-agent` / `kabuqina-acp`; retain old command aliases for one release |
| Core home env | only `HERMES_HOME` is authoritative | `KABUQINA_HOME` wins by key presence; missing new key falls back to `HERMES_HOME`; canonical APIs emit/read the new name |
| Standalone default home | `~/.hermes` | prefer `~/.kabuqina`; if only the old directory exists, read it for one release without copying or deleting it |
| Desktop home | `<data_dir>/hermes-home` | migrate old-only directory atomically to `<data_dir>/kabuqina-home`; if migration fails, use the old directory; if both exist, new wins and old is left untouched |
| Session / learning DBs | `state.db` and `learning.db` live below the selected home | filenames and schemas do not change; directory migration carries them together; tests use populated legacy samples |
| Keyring service | current service is `Kabuqina`; repository history used `HermesDesk` | read `Kabuqina` first; on miss read `HermesDesk` and copy to `Kabuqina`; clear removes both; never log plaintext |
| Gateway owner IDs | `gateway:<platform>:<hash>` | unchanged (contains no Hermes product identity) |
| Agent engine selector | removed by Step 5 | remains removed; no renamed escape hatch |
| Legal/upstream names | Nous Hermes model names, parser/protocol names, upstream URLs, archived releases, `LICENSE`/`NOTICE`/modification history | retained and classified, not mechanically renamed |

`hermes_core/` remains the monorepo source-tree boundary named by root
`AGENTS.md`; it is not an installed runtime namespace. Renaming that directory
would obscure upstream lineage and churn every build/document path without
changing the product contract.

## Order

### Task 1 — Home resolver and migration contracts

- [ ] Add canonical home/path APIs and deprecated aliases in core.
- [ ] Add Python desktop resolver with atomic old-only migration and safe
  fallback.
- [ ] Add Rust resolver with the same rules; route all desktop/gateway/cron
  paths through it.
- [ ] Cover new-wins, old-env fallback, old-dir fallback, old-only migration,
  both-exist, and populated `state.db` / `learning.db` samples.

### Task 2 — Credential migration

- [ ] Add current-first legacy-service lookup and copy-on-read.
- [ ] Delete both current and legacy credentials on explicit clear.
- [ ] Unit-test selection/migration control flow without exposing secrets.

### Task 3 — Canonical Python namespaces

- [ ] Move `hermes_cli` implementation to `kabuqina_cli` and migrate internal
  imports.
- [ ] Move the four top-level `hermes_*` modules to `kabuqina_*`; retain thin
  deprecated wrappers.
- [ ] Rename Kabuqina-owned classes/functions (`HermesCLI`, home/path helpers)
  and retain aliases only at compatibility seams.
- [ ] Update focused import and state/session tests before broad core tests.

### Task 4 — Distribution and bundle

- [ ] Rename pyproject distribution and canonical console scripts; retain old
  console aliases for one release.
- [ ] Update self-referential extras, lock/packaging metadata, bundled source
  destination, `.pth`, smoke imports, and bundle manifests.
- [ ] Prove the embedded runtime imports canonical modules without relying on
  compatibility shims.

### Task 5 — Guidance, scan, and observability

- [ ] Update active skills and user-facing setup guidance to Kabuqina commands,
  `KABUQINA_HOME`, and `~/.kabuqina`.
- [ ] Add one INFO migration log for desktop home and one for legacy keyring
  recovery; never include secret values.
- [ ] Classify every remaining tracked `hermes` hit as a compatibility alias,
  upstream/legal/history reference, model/protocol name, or defect.
- [ ] Record the persistence and compatibility decision in `DECISIONS.md`.

### Task 6 — Verification and close

- [ ] Run focused core/home/keyring tests, Python desktop tests, Web checks, and
  Rust tests/checks.
- [ ] Build/verify the Python bundle and run the package/import smoke tests.
- [ ] Run `git diff --check` and the final classified legacy-name scan.
- [ ] Commit A-R3 in reviewable slices, then record final evidence here.

## Non-goals

- Renaming Nous Hermes model families, ChatML/tool-call protocol identifiers,
  upstream URLs, or preserved legal attribution.
- Changing gateway owner IDs or database schemas.
- Reintroducing an engine selector under a Kabuqina name.
- Deleting compatibility shims in v0.4.0; their removal is a later explicit
  release task.
