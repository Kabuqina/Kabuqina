# Kabuqina Modifications to Hermes Core

`hermes_core/` is based on the upstream MIT-licensed **Hermes Agent** by
[Nous Research](https://nousresearch.com). It is maintained as an **owned core**
inside the Kabuqina monorepo and evolves independently — we do **not** auto-sync
from the upstream repository.

The following areas have been modified by Kabuqina Contributors to support
desktop-shell integration, Windows-specific policies, and student / academic
workflows:

> **TODO — awaiting review by the core development agent.**
>
> Please audit the git history of `hermes_core/` and list the modules / files
> that contain substantial Kabuqina-specific changes. For each entry include:
> - Path pattern or specific file
> - One-line description of the change
> - Whether it is a "patch" (small override) or "rewrite" (substantially new)
>
> Example format:
> ```markdown
> - `cron/scheduler.py` — Added `mode: notify` for fixed-text desktop reminders (patch)
> - `tools/cronjob_tools.py` — Extended job schema with `message` and `deliver` fields (patch)
> ```

## Unmodified upstream files

Files and directories not listed above remain substantially in their original
upstream form and are covered by the MIT license in `hermes_core/LICENSE`.
