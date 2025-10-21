"""
fix_errors.py
-------------

Automates fixing demisto-sdk validation errors:

- [BA106] Ensure content items have a valid `fromversion` (YAML) or `fromVersion` (JSON).
- [BA101] Ensure `id` equals `name` (for JSON and YAML items).
- [PA128] Ensure pack includes required files: `.secrets_ignore`, `.pack-ignore`, and `README.md`.

Usage:
    # Capture validator output
    demisto-sdk validate -g 2>&1 | tee sdk_errors.txt

    # Preview (no writes)
    python3 fix_errors.py sdk_errors.txt --dry-run

    # Apply fixes in-place (NO backups)
    python3 fix_errors.py sdk_errors.txt
    # or specify a repo root explicitly
    python3 fix_errors.py sdk_errors.txt --repo-root /absolute/path/to/repo

Options:
    sdk_output     Path to saved SDK validation output (e.g., sdk_errors.txt)
    --repo-root    Repo root to resolve relative paths (default: current dir)
    --dry-run      Show what would change without writing files

Notes:
    - YAML: sets/normalizes `fromversion` (lowercase). If YAML is malformed,
      falls back to a safe textual edit (regex/insert) and continues.
    - JSON: sets/normalizes `fromVersion` (camelCase); removes wrong-case key.
    - BA101 sets `id` = `name` (keeps human-readable ids).
    - PA128 creates missing files in pack root: `.secrets_ignore` (blank), `.pack-ignore`, `README.md`.
    - Minimum version applied for BA106 comes from the SDK line.
    - No backup files are created — commit first if you want rollback.
    - Easy to extend for more validation codes later.
"""
#!/usr/bin/env python3
import argparse
import json
import os
import re
import glob

# --- Optional YAML libs (ruamel preferred for formatting preservation) -------
try:
    from ruamel.yaml import YAML
    _HAVE_RUAMEL = True
except Exception:
    _HAVE_RUAMEL = False

try:
    import yaml as pyyaml
    _HAVE_PYYAML = True
except Exception:
    _HAVE_PYYAML = False

# --- Parsing helpers ---------------------------------------------------------

# Strip ANSI color codes that may appear in demisto-sdk output
ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')
def de_ansi(s: str) -> str:
    return ANSI_RE.sub('', s).strip()

# BA106 lines look like:
# Packs/foo/Playbooks/bar.yml: [BA106] - ... need at least 5.0.0, current is 0.0.0.
BA106_RE = re.compile(
    r'^(?P<path>[^:]+):\s*\[BA106\].*?need at least (?P<min>\d+\.\d+\.\d+)',
    re.IGNORECASE
)

# BA101 lines look like:
# Packs/.../layoutscontainer-foo.json: [BA101] - The name attribute (currently X) should be identical to its `id` attribute (Y)
BA101_RE = re.compile(
    r'^(?P<path>[^:]+):\s*\[BA101\].*?name attribute.*?\(currently (?P<name>.+?)\).*?id.*?\((?P<id>.+?)\)',
    re.IGNORECASE
)

# PA128 lines look like:
# Packs/soc-microsoft-defender: [PA128] - Packs require a .secrets_ignore, .pack-ignore and README
PA128_RE = re.compile(
    r'^(?P<pack>Packs/[A-Za-z0-9._\-]+):\s*\[PA128\]',
    re.IGNORECASE
)

SEMVER_NUM_RE = re.compile(r'\d+')

def parse_semver(v: str):
    if not v or not isinstance(v, str):
        return (0, 0, 0)
    parts = SEMVER_NUM_RE.findall(v)
    nums = [int(x) for x in parts[:3]]
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums[:3])

def max_version(a: str, b: str) -> str:
    return a if parse_semver(a) >= parse_semver(b) else b

def resolve_path(repo_root: str, rel_path: str) -> str:
    """
    Try multiple strategies to locate the referenced file robustly.
    """
    rp = rel_path.strip().rstrip(':').replace('\\', os.sep)

    # 1) Simple join
    p1 = os.path.normpath(os.path.join(repo_root, rp.lstrip('/')))
    if os.path.exists(p1):
        return p1

    # 2) As-is absolute
    if os.path.isabs(rp) and os.path.exists(rp):
        return rp

    # 3) Search for full tail under repo
    candidates = glob.glob(os.path.join(repo_root, '**', rp), recursive=True)
    if candidates:
        return sorted(candidates, key=lambda x: len(x))[0]

    # 4) Basename-only search fallback
    base = os.path.basename(rp)
    if base:
        hits = glob.glob(os.path.join(repo_root, '**', base), recursive=True)
        if hits:
            for h in hits:
                if h.replace('\\', '/').endswith(rp.replace('\\', '/')):
                    return h
            return sorted(hits, key=lambda x: len(x))[0]

    return p1  # caller can test existence and print SKIP if needed

# --- YAML/JSON IO ------------------------------------------------------------

def load_yaml(path):
    if _HAVE_RUAMEL:
        y = YAML()
        y.preserve_quotes = True
        with open(path, 'r', encoding='utf-8') as f:
            data = y.load(f)
        return (data if data is not None else {}), 'ruamel'
    elif _HAVE_PYYAML:
        with open(path, 'r', encoding='utf-8') as f:
            data = pyyaml.safe_load(f)
        return (data if data is not None else {}), 'pyyaml'
    else:
        raise RuntimeError("Need ruamel.yaml or PyYAML to parse YAML files.")

def dump_yaml(path, data, engine):
    if engine == 'ruamel':
        y = YAML()
        y.preserve_quotes = True
        with open(path, 'w', encoding='utf-8') as f:
            y.dump(data, f)
    else:
        with open(path, 'w', encoding='utf-8') as f:
            pyyaml.safe_dump(data, f, sort_keys=False)

# --- Textual fallback for malformed YAML ------------------------------------

FROMVERSION_LINE_RE = re.compile(r'(?mi)^(?P<indent>\s*)fromversion\s*:\s*(?P<val>[^\n#]+)')
ID_LINE_RE = re.compile(r'(?mi)^(?P<indent>\s*)id\s*:\s*(?P<val>[^\n#]+)')
NAME_LINE_RE = re.compile(r'(?mi)^(?P<indent>\s*)name\s*:\s*(?P<val>[^\n#]+)')

def textual_fix_yaml_fromversion(path: str, min_version: str, dry_run: bool):
    """
    Fallback when YAML parser fails. Tries to upgrade existing 'fromversion:'
    via regex; otherwise inserts a top-level 'fromversion: <min>' near the top.
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            text = f.read()
    except Exception as e:
        return False, f"ERROR (read fail): {path} -> {e}"

    m = FROMVERSION_LINE_RE.search(text)
    if m:
        cur_raw = (m.group('val') or '').strip().strip('"').strip("'")
        new_val = max_version(cur_raw or '0.0.0', min_version)
        if parse_semver(cur_raw) >= parse_semver(min_version):
            return False, f"OK (no change, textual): {path} (fromversion={cur_raw})"
        start, end = m.span('val')
        new_text = text[:start] + new_val + text[end:]
        if not dry_run:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_text)
        return True, f"UPDATED (textual): {path} -> fromversion={new_val}"

    # Insert near the top (after comments/doc markers)
    lines = text.splitlines(True)
    insert_idx = 0
    while insert_idx < len(lines):
        s = lines[insert_idx].lstrip()
        if s.startswith('---') or s.startswith('#') or s == '':
            insert_idx += 1
            continue
        break

    insert_line = f"fromversion: {min_version}\n"
    new_lines = lines[:insert_idx] + [insert_line] + lines[insert_idx:]
    if not dry_run:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(''.join(new_lines))
    return True, f"INSERTED (textual): {path} -> fromversion={min_version}"

def textual_fix_yaml_id_equals_name(path: str, dry_run: bool):
    """
    Fallback when YAML parser fails. Sets `id: <name>` via regex if both lines exist.
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            text = f.read()
    except Exception as e:
        return False, f"SKIP (read fail): {path} -> {e}"

    m_name = NAME_LINE_RE.search(text)
    if not m_name:
        return False, f"SKIP (no name found, textual): {path}"
    name_val = m_name.group('val').strip()

    if ID_LINE_RE.search(text):
        new_text = ID_LINE_RE.sub(lambda m: f"{m.group('indent')}id: {name_val}", text, count=1)
    else:
        # No id line: insert an id right after name
        idx = m_name.end()
        new_text = text[:idx] + f"\n{m_name.group('indent')}id: {name_val}" + text[idx:]

    if not dry_run:
        with open(path, 'w', encoding='utf-8') as wf:
            wf.write(new_text)
    return True, f"UPDATED (textual): {path} -> id={name_val}"

# --- BA106 fixers ------------------------------------------------------------

def fix_yaml_fromversion(path: str, min_version: str, dry_run: bool):
    # Try structured YAML first; on failure, do textual fallback
    try:
        data, engine = load_yaml(path)
    except Exception:
        return textual_fix_yaml_fromversion(path, min_version, dry_run)

    lower = str(data.get('fromversion') or '')
    camel = str(data.get('fromVersion') or '')
    effective = lower or ''
    if camel and parse_semver(camel) > parse_semver(effective or '0.0.0'):
        effective = camel

    new_val = max_version(effective or '0.0.0', min_version)

    if effective and parse_semver(effective) >= parse_semver(min_version):
        if 'fromVersion' in data and 'fromversion' not in data:
            if not dry_run:
                data['fromversion'] = camel
                del data['fromVersion']
                dump_yaml(path, data, engine)
            return True, f"NORMALIZED: {path} -> fromVersion→fromversion={camel}"
        return False, f"OK (no change): {path} (fromversion={effective})"

    if 'fromVersion' in data:
        data.pop('fromVersion', None)
    data['fromversion'] = new_val
    if not dry_run:
        dump_yaml(path, data, engine)
    return True, f"UPDATED: {path} -> fromversion={new_val}"

def fix_json_fromversion(path: str, min_version: str, dry_run: bool):
    with open(path, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return False, f"SKIP (invalid JSON): {path}"

    camel = str(data.get('fromVersion') or '')
    wrong = str(data.get('fromversion') or '')
    effective = camel or ''
    if wrong and parse_semver(wrong) > parse_semver(effective or '0.0.0'):
        effective = wrong

    new_val = max_version(effective or '0.0.0', min_version)

    if effective and parse_semver(effective) >= parse_semver(min_version):
        changed = False
        if 'fromversion' in data and 'fromVersion' not in data:
            data['fromVersion'] = data['fromversion']
            del data['fromversion']
            changed = True
        if changed and not dry_run:
            with open(path, 'w', encoding='utf-8') as wf:
                json.dump(data, wf, indent=2, ensure_ascii=False)
            return True, f"NORMALIZED: {path} -> fromversion→fromVersion={data['fromVersion']}"
        return False, f"OK (no change): {path} (fromVersion={effective})"

    data['fromVersion'] = new_val
    if 'fromversion' in data:
        del data['fromversion']
    if not dry_run:
        with open(path, 'w', encoding='utf-8') as wf:
            json.dump(data, wf, indent=2, ensure_ascii=False)
    return True, f"UPDATED: {path} -> fromVersion={new_val}"

def fix_file_ba106(path: str, min_version: str, dry_run: bool = False):
    ext = os.path.splitext(path)[1].lower()
    if not os.path.exists(path):
        return False, f"SKIP (missing): {path}"
    if ext in ('.yml', '.yaml'):
        return fix_yaml_fromversion(path, min_version, dry_run)
    if ext == '.json':
        return fix_json_fromversion(path, min_version, dry_run)
    return False, f"SKIP (unknown ext): {path}"

# --- BA101 fixers (id = name) ------------------------------------------------

def fix_id_name(path: str, dry_run: bool = False):
    ext = os.path.splitext(path)[1].lower()
    if not os.path.exists(path):
        return False, f"SKIP (missing): {path}"

    if ext == '.json':
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            return False, f"SKIP (bad JSON): {path} -> {e}"

        nm = data.get('name')
        idv = data.get('id')
        if nm is None:
            return False, f"SKIP (no name): {path}"
        if nm == idv:
            return False, f"OK (no change): {path} (id=name={nm})"
        if not dry_run:
            data['id'] = nm
            with open(path, 'w', encoding='utf-8') as wf:
                json.dump(data, wf, indent=2, ensure_ascii=False)
        return True, f"UPDATED: {path} -> id={nm}"

    elif ext in ('.yml', '.yaml'):
        # Try structured first
        try:
            data, engine = load_yaml(path)
            nm = data.get('name')
            idv = data.get('id')
            if nm is None:
                return False, f"SKIP (no name): {path}"
            if nm == idv:
                return False, f"OK (no change): {path} (id=name={nm})"
            if not dry_run:
                data['id'] = nm
                dump_yaml(path, data, engine)
            return True, f"UPDATED: {path} -> id={nm}"
        except Exception:
            # Fallback textual edit
            return textual_fix_yaml_id_equals_name(path, dry_run)

    return False, f"SKIP (unsupported ext): {path}"

# --- PA128 fixers (pack required files) --------------------------------------

def fix_pack_required_files(pack_root: str, dry_run: bool = False):
    created = []
    targets = {
        ".secrets-ignore": "",                           # <-- hyphen here
        ".pack-ignore": "# Add ignore rules here\n",
        "README.md": f"# {os.path.basename(pack_root)}\n"
    }
    for fname, content in targets.items():
        fpath = os.path.join(pack_root, fname)
        if not os.path.exists(fpath):
            if not dry_run:
                os.makedirs(pack_root, exist_ok=True)
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(content)
            created.append(fname)
    if created:
        return True, f"CREATED in {pack_root}: {', '.join(created)}"
    return False, f"OK (no change): {pack_root} has required files"


# --- Main --------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Fix BA106 (fromversion), BA101 (id=name), and PA128 (pack required files).")
    ap.add_argument("sdk_output", help="Path to saved SDK validation output (e.g., sdk_errors.txt)")
    ap.add_argument("--repo-root", default=".", help="Repo root (default: current dir)")
    ap.add_argument("--dry-run", action="store_true", help="Show what would change without writing files")
    args = ap.parse_args()

    repo_root = os.path.abspath(args.repo_root)

    total = 0
    changes = 0
    with open(args.sdk_output, 'r', encoding='utf-8', errors='ignore') as f:
        for raw in f:
            line = de_ansi(raw)

            # PA128
            m128 = PA128_RE.search(line)
            if m128:
                total += 1
                pack_rel = m128.group('pack').strip().rstrip(':').replace('\\', os.sep)
                pack_root = resolve_path(repo_root, pack_rel)
                if not os.path.exists(pack_root):
                    print(f"SKIP (missing pack): raw='{raw.rstrip()}' parsed='{line}' rel='{pack_rel}' resolved='{pack_root}'")
                    continue
                changed, msg = fix_pack_required_files(pack_root, args.dry_run)
                print(msg)
                if changed:
                    changes += 1
                continue

            # BA101
            m101 = BA101_RE.search(line)
            if m101:
                total += 1
                rel_path = m101.group('path').strip().rstrip(':').replace('\\', os.sep)
                resolved = resolve_path(repo_root, rel_path)
                if not os.path.exists(resolved):
                    print(f"SKIP (missing): raw='{raw.rstrip()}'  parsed='{line}'  rel='{rel_path}'  resolved='{resolved}'")
                    continue
                changed, msg = fix_id_name(resolved, args.dry_run)
                print(msg)
                if changed:
                    changes += 1
                continue

            # BA106
            m106 = BA106_RE.search(line)
            if m106:
                total += 1
                rel_path = m106.group('path').strip().rstrip(':').replace('\\', os.sep)
                resolved = resolve_path(repo_root, rel_path)
                if not os.path.exists(resolved):
                    print(f"SKIP (missing): raw='{raw.rstrip()}'  parsed='{line}'  rel='{rel_path}'  resolved='{resolved}'")
                    continue
                min_ver = m106.group('min').strip()
                changed, msg = fix_file_ba106(resolved, min_ver, args.dry_run)
                print(msg)
                if changed:
                    changes += 1
                continue

            # ignore other lines

    print(f"\nMatched BA101/BA106/PA128 lines: {total}. Files changed: {changes}. Dry-run: {args.dry_run}")

if __name__ == "__main__":
    main()
