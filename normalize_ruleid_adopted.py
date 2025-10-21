#!/usr/bin/env python3
# normalize_ruleid_adopted.py
#
# Pre-validation normalizer for XSIAM/XSOAR packs:
#  - Cleans xsoar_config.json marketplace_packs (removes blanks/dupes/invalid IDs)
#  - Ensures required deps in pack_metadata.json and xsoar_config.json (when --require provided)
#  - Adds pre/post config docs entries IF corresponding files exist (and flags if missing unless --fix)
#  - (Placeholder) normalization for rule_id/adopted
#
# Usage examples:
#   python3 normalize_ruleid_adopted.py --root Packs/soc-trendmicro-visionone
#   python3 normalize_ruleid_adopted.py --root Packs/soc-trendmicro-visionone --fix
#   python3 normalize_ruleid_adopted.py --root Packs/soc-trendmicro-visionone \
#       --require TrendMicroVisionOneV3:"Trend Micro Vision One" --fix

import argparse
import json
import os
import re
import sys
from typing import Dict, List, Tuple

# -----------------------------
# Helpers
# -----------------------------
def _load_json(path: str) -> Tuple[dict, bool]:
    if not os.path.exists(path):
        return {}, False
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f), True

def _dump_json(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

def _find_file(root: str, filename: str) -> str:
    for dirpath, _dirnames, filenames in os.walk(root):
        if filename in filenames:
            return os.path.join(dirpath, filename)
    return ""

def _parse_require_list(items: List[str]) -> Dict[str, str]:
    """
    Accepts entries like:
      TrendMicroVisionOneV3
      TrendMicroVisionOneV3:"Trend Micro Vision One"
    Returns { "TrendMicroVisionOneV3": "Trend Micro Vision One" (or "") }
    Ignores empty / malformed entries safely.
    """
    out: Dict[str, str] = {}
    if not items:
        return out
    for raw in items:
        if raw is None:
            continue
        raw = str(raw).strip()
        if not raw or raw == "--require":
            continue
        if ":" in raw:
            dep_id, display = raw.split(":", 1)
            dep_id = dep_id.strip()
            display = display.strip().strip('"').strip("'")
            if dep_id:
                out[dep_id] = display
        else:
            if raw:
                out[raw] = ""
    return out

def _infer_repo_base_from_xsoar_config(xsoar_cfg: dict) -> str:
    """
    Try to infer https://github.com/<owner>/<repo> from custom_packs[0].url
    e.g. https://github.com/ORG/REPO/archive/refs/tags/v1.0.7.zip -> https://github.com/ORG/REPO
    """
    cps = xsoar_cfg.get("custom_packs") or []
    if not cps:
        return ""
    url = cps[0].get("url") or ""
    m = re.match(r"https://github.com/([^/]+)/([^/]+)/", url)
    if m:
        owner, repo = m.group(1), m.group(2)
        return f"https://github.com/{owner}/{repo}"
    return ""

def _safe_add_doc_entry(doc_list: list, name: str, url: str) -> bool:
    """
    Add a single doc entry if an entry with the same URL or same Name doesn't already exist.
    Returns True if modified.
    """
    for item in doc_list:
        if not isinstance(item, dict):
            continue
        if item.get("url") == url or item.get("name") == name:
            return False
    doc_list.append({"name": name, "url": url})
    return True

# -----------------------------
# Always sanitize marketplace_packs
# -----------------------------
def clean_xsoar_marketplace_packs(xsoar_config_path: str, fix: bool) -> bool:
    """
    Sanitize marketplace_packs:
      - remove entries with missing/blank/whitespace/invalid ids
      - de-duplicate by id (keep first)
    Returns True if a change was made (and written when fix=True).
    """
    data, ok = _load_json(xsoar_config_path)
    if not ok:
        return False

    mp = data.get("marketplace_packs") or []
    if not isinstance(mp, list):
        return False

    def valid_id(x: str) -> bool:
        # Accept IDs starting with alnum and then alnum/underscore/dot/dash
        return bool(re.match(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$", x))

    seen = set()
    cleaned = []
    changed = False

    for item in mp:
        if not isinstance(item, dict):
            changed = True
            continue
        _id = str(item.get("id", "")).strip()
        if not _id or not valid_id(_id):
            changed = True
            continue
        if _id in seen:
            changed = True
            continue
        seen.add(_id)
        cleaned.append({"id": _id, "version": item.get("version", "latest")})

    if cleaned != mp:
        changed = True

    if changed:
        data["marketplace_packs"] = cleaned
        if fix:
            _dump_json(xsoar_config_path, data)

    return changed

# -----------------------------
# Dependency checks / fixes
# -----------------------------
def ensure_pack_metadata_deps(pack_metadata_path: str,
                              reqs: Dict[str, str],
                              fix: bool) -> List[str]:
    missing = []
    data, ok = _load_json(pack_metadata_path)
    if not ok:
        return [f"pack_metadata.json not found at {pack_metadata_path}"]

    deps = data.get("dependencies") or {}
    changed = False
    for dep_id, display_name in reqs.items():
        dep_id = str(dep_id or "").strip()
        if not dep_id:
            continue
        if dep_id not in deps:
            missing.append(f"{dep_id} (pack_metadata.json)")
            if fix:
                deps[dep_id] = {"mandatory": True}
                if display_name:
                    deps[dep_id]["display_name"] = display_name
                changed = True

    if changed and fix:
        data["dependencies"] = deps
        _dump_json(pack_metadata_path, data)

    return missing

def ensure_xsoar_config_deps(xsoar_config_path: str,
                             reqs: Dict[str, str],
                             fix: bool) -> List[str]:
    missing = []
    data, ok = _load_json(xsoar_config_path)
    if not ok:
        return [f"xsoar_config.json not found at {xsoar_config_path}"]

    mp = data.get("marketplace_packs") or []
    have = {item.get("id"): item for item in mp if isinstance(item, dict) and item.get("id")}
    changed = False

    for dep_id in reqs.keys():
        dep_id = str(dep_id or "").strip()
        if not dep_id:
            continue  # skip empty/whitespace IDs
        if dep_id not in have:
            missing.append(f"{dep_id} (xsoar_config.json)")
            if fix:
                mp.append({"id": dep_id, "version": "latest"})
                changed = True

    # Defensive cleanup (in case prior runs polluted the file)
    clean_mp = [p for p in mp if isinstance(p, dict) and str(p.get("id", "")).strip()]
    if clean_mp != mp:
        changed = True
        mp = clean_mp

    if changed and fix:
        data["marketplace_packs"] = mp
        _dump_json(xsoar_config_path, data)

    return missing

# -----------------------------
# Pre/Post config README → xsoar_config.json
# -----------------------------
def ensure_xsoar_config_docs(xsoar_config_path: str,
                             pack_metadata_path: str,
                             repo_root: str,
                             fix: bool) -> List[str]:
    """
    If PRE_CONFIG_README.md or POST_CONFIG_README.md exist in the repo:
      - If xsoar_config.json is missing the corresponding entry → flag it.
      - If --fix is set → add the entry.
    If the files don't exist, do nothing.
    """
    issues: List[str] = []
    xcfg, ok_cfg = _load_json(xsoar_config_path)
    if not ok_cfg:
        return [f"xsoar_config.json not found at {xsoar_config_path}"]

    pmeta, _ok_meta = _load_json(pack_metadata_path)
    pack_display_name = pmeta.get("name") or "Pack"

    pre_path = _find_file(repo_root, "PRE_CONFIG_README.md")
    post_path = _find_file(repo_root, "POST_CONFIG_README.md")

    # If neither file exists, silently skip
    if not pre_path and not post_path:
        return issues

    base_repo = _infer_repo_base_from_xsoar_config(xcfg)
    def mk_url(filename: str) -> str:
        return f"{base_repo}/blob/main/{filename}" if base_repo else filename

    changed = False

    # ---- PRE CONFIG DOC ----
    if pre_path:
        pre_docs = xcfg.get("pre_config_docs") or []
        pre_name = f"{pack_display_name} - Pre-Automation Steps"
        pre_url = mk_url("PRE_CONFIG_README.md")
        has_pre = any(
            isinstance(d, dict)
            and (d.get("url") == pre_url or d.get("name") == pre_name)
            for d in pre_docs
        )
        if not has_pre:
            issues.append("Missing pre_config_docs entry for PRE_CONFIG_README.md")
            if fix:
                _safe_add_doc_entry(pre_docs, pre_name, pre_url)
                xcfg["pre_config_docs"] = pre_docs
                changed = True

    # ---- POST CONFIG DOC ----
    if post_path:
        post_docs = xcfg.get("post_config_docs") or []
        post_name = f"{pack_display_name} - Manual Steps"
        post_url = mk_url("POST_CONFIG_README.md")
        has_post = any(
            isinstance(d, dict)
            and (d.get("url") == post_url or d.get("name") == post_name)
            for d in post_docs
        )
        if not has_post:
            issues.append("Missing post_config_docs entry for POST_CONFIG_README.md")
            if fix:
                _safe_add_doc_entry(post_docs, post_name, post_url)
                xcfg["post_config_docs"] = post_docs
                changed = True

    if changed and fix:
        _dump_json(xsoar_config_path, xcfg)

    return issues

# -----------------------------
# Normalization (placeholder)
# -----------------------------
def normalize_ruleid_and_adopted(root: str, dry_run: bool) -> None:
    """
    Placeholder for your existing logic that:
      - sets correlation rule_id to 0 where applicable
      - ensures adopted: true where required (NOT applied to modeling rules)
    """
    return

# -----------------------------
# Main
# -----------------------------
def main():
    ap = argparse.ArgumentParser(description="Normalize pack and enforce dependencies + docs.")
    ap.add_argument("--root", default=".", help="Repo root (one-pack-per-repo).")
    ap.add_argument("--require", action="append", default=[],
                    help="Required dependency. Format: ID or ID:\"Display Name\". Repeatable.")
    ap.add_argument("--fix", action="store_true", help="Auto-fix missing deps/docs in files.")
    ap.add_argument("--dry-run", action="store_true", help="Do not write any changes.")
    args = ap.parse_args()

    reqs = _parse_require_list(args.require)

    # Locate files
    pack_metadata_path = _find_file(args.root, "pack_metadata.json")
    xsoar_config_path  = _find_file(args.root, "xsoar_config.json")

    # If dry-run (without --fix), avoid writes
    global _dump_json
    if args.dry_run and not args.fix:
        def _noop_dump_json(path, data):  # type: ignore
            print(f"[DRY-RUN] Would update {path}")
        _dump_json = _noop_dump_json  # type: ignore

    # 0) Always sanitize marketplace_packs (even if no --require provided)
    cleaned = clean_xsoar_marketplace_packs(xsoar_config_path, fix=args.fix)
    if cleaned and not args.fix:
        print("[INFO] marketplace_packs contained invalid/duplicate entries. Run with --fix to clean.")

    # 1) Normalization placeholder
    normalize_ruleid_and_adopted(args.root, args.dry_run)

    # 2) Dependency checks (only if --require provided)
    errors: List[str] = []
    if reqs:
        errors += ensure_pack_metadata_deps(pack_metadata_path, reqs, fix=args.fix)
        errors += ensure_xsoar_config_deps(xsoar_config_path, reqs, fix=args.fix)
    else:
        print("No --require deps provided; skipping dependency checks.")

    # 3) Ensure pre/post config docs if PRE/POST README files exist
    errors += ensure_xsoar_config_docs(xsoar_config_path, pack_metadata_path, args.root, fix=args.fix)

    if errors and not args.fix:
        print("Missing required items:\n  - " + "\n  - ".join(errors))
        sys.exit(2)

    if not errors:
        print("✅ Checks passed.")
    else:
        print("✅ Missing items were auto-fixed:")
        for e in errors:
            print(f"  - {e}")

if __name__ == "__main__":
    main()
