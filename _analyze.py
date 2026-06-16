import os, sys

base = "d:/project/Kabuqina/hermes_core"

def count_lines(path):
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except:
        return 0

def scan_dir(dirpath, label=None):
    if label:
        print(f"\n=== {label}: {dirpath} ===")
    else:
        print(f"\n=== {dirpath} ===")
    if not os.path.isdir(dirpath):
        print("  (not found)")
        return
    for f in sorted(os.listdir(dirpath)):
        full = os.path.join(dirpath, f)
        if os.path.isfile(full):
            lc = count_lines(full)
            print(f"  {f} | {lc} lines")
        elif os.path.isdir(full):
            print(f"  [dir] {f}/")

# 1. Top-level .py files
print("=" * 60)
print("TOP-LEVEL .py FILES")
print("=" * 60)
for f in sorted(os.listdir(base)):
    full = os.path.join(base, f)
    if f.endswith(".py") and os.path.isfile(full):
        lc = count_lines(full)
        print(f"  {f} | {lc} lines")

# 2. agent/ directory
scan_dir(os.path.join(base, "agent"), "AGENT DIR")

# 3. tools/ directory
scan_dir(os.path.join(base, "tools"), "TOOLS DIR")

# 4. hermes_cli/ directory
scan_dir(os.path.join(base, "hermes_cli"), "HERMES_CLI DIR")

# 5. Other subdirs
for sub in ["gateway", "cron", "skills", "plugins", "environments", "web", 
            "acp_adapter", "acp_registry", "ui-tui", "tui_gateway",
            "optional-skills", "scripts", "tests", "website"]:
    scan_dir(os.path.join(base, sub), f"SUBDIR: {sub}")

# 6. Top-level non-py files
print("\n" + "=" * 60)
print("TOP-LEVEL NON-PY FILES")
print("=" * 60)
for f in sorted(os.listdir(base)):
    full = os.path.join(base, f)
    if not f.endswith(".py") and os.path.isfile(full):
        lc = count_lines(full)
        print(f"  {f} | {lc} lines")
