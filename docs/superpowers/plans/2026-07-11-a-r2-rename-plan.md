# A-R2 desktop / web internal rename plan

## Scope

Rename the Kabuqina-owned desktop and web identifiers from `hermesdesk` /
`HermesDesk` to `kabuqina` / `Kabuqina`. Keep the old bridge header, route,
environment variables, settings keys, and browser storage readable for one
release. This slice excludes `hermes_core/`, `HERMES_HOME`, `hermes-home`,
`hermes_cli`, and other persistence/core names reserved for A-R3.

## Order

1. Add dual-read compatibility at the Python desk boundary and Tauri bridge.
   New Kabuqina names are emitted; legacy names are accepted only at the
   boundary.
2. Migrate Tauri command names, web readiness/session identifiers, capability
   routes, and product logger prefixes. Keep deprecated bridge aliases where a
   separately-versioned child could still call them.
3. Migrate settings and browser storage with read-old/write-new semantics.
4. Update focused unit tests, run Python/TypeScript/Rust checks, then scan the
   three owned source roots to ensure remaining Hermes names are either core
   references, persistence names reserved for A-R3, or explicit compatibility
   aliases.

## Non-overlap

Do not edit B3-owned `hermes_core/learning/practice_generator.py`,
`hermes_core/tests/learning/test_practice_generator.py`, or
`python/src/desk_server/routes/study_routes.py`.
