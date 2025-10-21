#!/usr/bin/env python3
import argparse, json, re, sys, hashlib, hmac
from typing import Any, List, Optional, Pattern, Callable, Tuple

try:
    import yaml  # optional, only needed if --config is used
except Exception:
    yaml = None

# ---------------- Helpers ----------------
def digest4(text: str, salt: Optional[str]) -> str:
    if salt:
        return hmac.new(salt.encode(), text.encode(), hashlib.sha256).hexdigest()[:4]
    return hashlib.sha256(text.encode()).hexdigest()[:4]

def luhn_valid(num: str) -> bool:
    s = ''.join(ch for ch in num if ch.isdigit())
    if not (13 <= len(s) <= 19): return False
    total, double = 0, False
    for ch in reversed(s):
        d = ord(ch) - 48
        if double:
            d *= 2
            if d > 9: d -= 9
        total += d
        double = not double
    return total % 10 == 0

# ---------------- Patterns ----------------
class Pat:
    def __init__(self, name: str, regex: str, tag: str,
                 validate: Optional[Callable[[str], bool]]=None,
                 allowlist_key: Optional[str]=None):
        self.name = name
        self.re: Pattern[str] = re.compile(regex, re.IGNORECASE)
        self.tag = tag
        self.validate = validate
        self.allowlist_key = allowlist_key  # "domains" or "hosts"

def defaults() -> List[Pat]:
    return [
        # IPv4 and basic IPv6
        Pat("IP", r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d?\d)(?:\.(?!$)|$)){4}\b"
                  r"|(?:(?:[A-F0-9]{1,4}:){1,7}[A-F0-9]{1,4}|::1|::)", "IP"),
        # Emails (capture domain for allowlist)
        Pat("EMAIL", r"\b[a-z0-9._%+-]+@([a-z0-9.-]+\.[a-z]{2,})\b", "EMAIL", allowlist_key="domains"),
        # Domains (avoid paths)
        Pat("DOMAIN", r"\b([a-z0-9.-]+\.[a-z]{2,})\b", "DOMAIN", allowlist_key="domains"),
        # Hostnames (simple; we also tag FQDN fragments)
        Pat("HOST", r"\b([a-z0-9][a-z0-9-]{0,62})(?:\.[a-z0-9.-]+)?\b", "HOST", allowlist_key="hosts"),
        # MAC
        Pat("MAC", r"\b([0-9A-F]{2}[:-]){5}([0-9A-F]{2})\b", "MAC"),
        # GUID/UUID v1-5
        Pat("GUID", r"\b[a-f0-9]{8}-[a-f0-9]{4}-[1-5][a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}\b", "GUID"),
        # URLs
        Pat("URL", r"\bhttps?://[^\s\"'>)]+", "URL"),
        # JWT
        Pat("JWT", r"\beyJ[0-9A-Za-z_\-]+=*\.[0-9A-Za-z_\-]+=*\.[0-9A-Za-z_\-]+=*\b", "JWT"),
        # Common API key formats (heuristic)
        Pat("KEY", r"\b(?:sk-|AKIA|ghp_|ya29\.)[A-Za-z0-9_\-]{10,}\b|\b[a-f0-9]{32,64}\b|\b[0-9A-Za-z_\-]{24,}\b", "KEY"),
        # Credit cards (with Luhn)
        Pat("CREDITCARD", r"\b(?:\d[ -]*?){13,19}\b", "CC", validate=luhn_valid),
        # US SSN
        Pat("SSN", r"\b\d{3}-\d{2}-\d{4}\b", "SSN"),
        # File paths (Windows/Unix)
        Pat("PATH", r"(?:\b/[^\s:]+|\b[A-Za-z]:\\[^\s:]+)", "PATH"),
        # Basic user extraction inside strings
        Pat("USER", r'(?:(?i)\buser(name)?\s*[:=]\s*"?)([A-Za-z0-9._\\-]{1,64})', "USER"),
    ]

# ---------------- Config ----------------
class Config:
    def __init__(self):
        self.allow_domains: List[str] = []
        self.allow_hosts: List[str] = []
        self.keys_exact: List[str] = []
        self.keys_ci: List[str] = []
        self.scan_value_keys_ci: List[str] = []
        self.disabled: List[str] = []
        self.custom: List[Tuple[str,str,str]] = []  # (name, pattern, tag)

    @staticmethod
    def from_yaml(path: Optional[str]) -> "Config":
        cfg = Config()
        if not path:
            return cfg
        if yaml is None:
            raise RuntimeError("PyYAML is not installed; omit --config or install pyyaml.")
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        al = data.get("allowlist", {})
        cfg.allow_domains = list(al.get("domains", []))
        cfg.allow_hosts = list(al.get("hosts", []))
        cfg.keys_exact = list(data.get("keys_exact", []))
        cfg.keys_ci = list(data.get("keys_ci", []))
        cfg.scan_value_keys_ci = list(data.get("scan_value_keys_ci", []))
        cfg.disabled = list(data.get("disable_patterns", []))
        for item in data.get("custom_patterns", []):
            cfg.custom.append((item.get("name","CUSTOM"), item["pattern"], item.get("tag","CUSTOM")))
        return cfg

# ---------------- Redactor ----------------
class Redactor:
    def __init__(self, salt: Optional[str], cfg: Config):
        self.salt = salt
        # Build patterns
        pats = [p for p in defaults() if p.name.upper() not in {d.upper() for d in cfg.disabled}]
        for name, pattern, tag in cfg.custom:
            pats.append(Pat(name, pattern, tag))
        self.pats: List[Pat] = pats

        # Allowlists
        self.allow_domains = [d.lower() for d in cfg.allow_domains]
        self.allow_hosts = [h.lower() for h in cfg.allow_hosts]

        # Key policies
        self.keys_exact = set(cfg.keys_exact)
        self.keys_ci = [k.lower() for k in cfg.keys_ci]
        self.scan_keys_ci = [k.lower() for k in cfg.scan_value_keys_ci]

    # ---- allow rules for EMAIL/DOMAIN/HOST ----
    def _is_allowed(self, pat: Pat, text: str, match: re.Match) -> bool:
        if pat.allowlist_key == "domains":
            candidates = [match.group(m) for m in range(1, (match.lastindex or 0)+1) if match.group(m)]
            for cand in candidates or [text]:
                if any(cand.lower().endswith(suf) for suf in self.allow_domains):
                    return True
        elif pat.allowlist_key == "hosts":
            candidates = [match.group(m) for m in range(1, (match.lastindex or 0)+1) if match.group(m)]
            for cand in candidates or [text]:
                if cand.lower() in self.allow_hosts:
                    return True
        return False

    def _sub(self, pat: Pat, s: str) -> str:
        def repl(m: re.Match) -> str:
            whole = m.group(0)
            if self._is_allowed(pat, whole, m):
                return whole
            if pat.validate and not pat.validate(whole):
                return whole
            return f"[{pat.tag}:{digest4(whole, self.salt)}]"
        return pat.re.sub(repl, s)

    def redact_string(self, s: str) -> str:
        out = s
        for pat in self.pats:
            out = self._sub(pat, out)
        return out

    def _key_should_replace_entire_value(self, key: str) -> bool:
        if key in self.keys_exact: return True
        lk = key.lower()
        return any(lk == k for k in self.keys_ci)

    def _key_should_scan_value(self, key: str) -> bool:
        lk = key.lower()
        return any(lk == k for k in self.scan_keys_ci)

    def redact_value_for_key(self, key: str, value: Any) -> Any:
        # If key is marked to fully redact: replace entire value with a token (stable per original string/json)
        if self._key_should_replace_entire_value(key):
            j = json.dumps(value, sort_keys=True, ensure_ascii=False)
            return f"[REDACTED:{digest4(key + '|' + j, self.salt)}]"
        # If it's a string under a "scan" key or any other string: run pattern scans
        if isinstance(value, str):
            return self.redact_string(value)
        return None  # means "no special handling"

    def walk(self, node: Any, parent_key: Optional[str]=None) -> Any:
        if isinstance(node, dict):
            for k, v in list(node.items()):
                # key-driven handling
                replaced = self.redact_value_for_key(k, v)
                if replaced is not None:
                    node[k] = replaced
                    continue
                # recurse
                node[k] = self.walk(v, k)
            return node
        elif isinstance(node, list):
            return [self.walk(v, parent_key) for v in node]
        elif isinstance(node, str):
            # If we're under a "scan" key, run scans; otherwise still scan strings (safe default)
            return self.redact_string(node)
        else:
            return node

# ---------------- Main ----------------
def parse_args():
    ap = argparse.ArgumentParser(description="Redact sensitive data in JSON while preserving schema (JSON in → JSON out).")
    ap.add_argument("-i","--input", help="Input JSON file (default: stdin)")
    ap.add_argument("-o","--output", help="Output JSON file (default: stdout)")
    ap.add_argument("--salt", help="Optional HMAC salt for stable tokens across files")
    ap.add_argument("--config", help="Optional YAML config for keys/patterns/allowlists")
    ap.add_argument("--indent", type=int, default=None, help="Pretty-print JSON with this indent")
    return ap.parse_args()

def load_json(path: Optional[str]) -> Any:
    data = sys.stdin.read() if not path else open(path, "r", encoding="utf-8").read()
    return json.loads(data)

def dump_json(obj: Any, path: Optional[str], indent: Optional[int]):
    txt = json.dumps(obj, ensure_ascii=False, separators=(",", ":"), indent=indent)
    if not path:
        sys.stdout.write(txt)
        if indent is not None: sys.stdout.write("\n")
    else:
        with open(path, "w", encoding="utf-8") as f:
            f.write(txt)
            if indent is not None: f.write("\n")

def main():
    args = parse_args()
    cfg = Config.from_yaml(args.config)
    red = Redactor(args.salt, cfg)
    try:
        doc = load_json(args.input)
    except json.JSONDecodeError as e:
        sys.stderr.write(f"ERROR: Input is not valid JSON: {e}\n")
        sys.exit(1)
    redacted = red.walk(doc)
    dump_json(redacted, args.output, args.indent)

if __name__ == "__main__":
    main()
