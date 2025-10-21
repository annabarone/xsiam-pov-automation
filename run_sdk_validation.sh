#!/usr/bin/env bash
# run_sdk_validation.sh
# Usage:
#   ./run_sdk_validation.sh <PACK_PATH> [--revalidate] [extra normalize args...]
#
# Examples:
#   ./run_sdk_validation.sh Packs/soc-trendmicro-visionone
#   ./run_sdk_validation.sh Packs/soc-trendmicro-visionone --revalidate --require TrendMicroVisionOneV3 --fix

set -euo pipefail

# --- Colors ---
if [ -t 1 ]; then
  RED="$(printf '\033[31m')" ; GRN="$(printf '\033[32m')" ; YLW="$(printf '\033[33m')" ; BLU="$(printf '\033[34m')" ; RST="$(printf '\033[0m')"
else
  RED="" ; GRN="" ; YLW="" ; BLU="" ; RST=""
fi

if [ $# -lt 1 ]; then
  echo "Usage: $0 <PACK_PATH> [--revalidate] [extra normalize args...]"
  exit 1
fi

PACK_PATH="$1"
shift || true

# Flags
REVALIDATE=false
declare -a EXTRA_ARGS=()   # <<< ensure array is declared

while (( "$#" )); do
  case "$1" in
    --revalidate)
      REVALIDATE=true
      shift
      ;;
    *)
      EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

# Pick python
if command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  PY=python
fi

# --- 1) Normalize (pre-validation) ---
echo -e "${BLU}[*] Normalizing pack content with normalize_ruleid_adopted.py${RST}"
set +e
# safe expansion even if EXTRA_ARGS is empty
$PY normalize_ruleid_adopted.py --root "$PACK_PATH" ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}
NORM_RC=$?
set -e
if [ $NORM_RC -ne 0 ]; then
  echo -e "${RED}[!] normalize_ruleid_adopted.py exited with code $NORM_RC${RST}"
  exit $NORM_RC
fi

# --- 2) demisto-sdk validate (capture output even on failure) ---
echo -e "${BLU}[*] Running demisto-sdk validate for ${PACK_PATH}${RST}"
set +e
demisto-sdk validate -i "$PACK_PATH" -g 2>&1 | tee sdk_errors.txt
SDK_RC=${PIPESTATUS[0]}
set -e

if [ $SDK_RC -eq 0 ]; then
  echo -e "${GRN}[✓] demisto-sdk validate passed with no errors.${RST}"
else
  echo -e "${YLW}[!] demisto-sdk validate returned code ${SDK_RC}. Proceeding to auto-fix…${RST}"
fi

# --- 3) Post-validation auto-fix from SDK output ---
if [ -s sdk_errors.txt ]; then
  echo -e "${BLU}[*] Running fix_errors.py on sdk_errors.txt${RST}"
  set +e
  $PY fix_errors.py sdk_errors.txt
  FIX_RC=$?
  set -e
  if [ $FIX_RC -ne 0 ]; then
    echo -e "${RED}[!] fix_errors.py exited with code $FIX_RC${RST}"
  else
    echo -e "${GRN}[✓] Applied fixes from fix_errors.py${RST}"
  fi
else
  echo -e "${GRN}[✓] No sdk_errors.txt content to fix (empty).${RST}"
fi

# --- 4) Optional re-validate after fixes ---
if $REVALIDATE; then
  echo -e "${BLU}[*] Re-running demisto-sdk validate after fixes…${RST}"
  set +e
  demisto-sdk validate -i "$PACK_PATH" -g 2>&1 | tee sdk_errors.txt
  SDK_RC2=${PIPESTATUS[0]}
  set -e
  if [ $SDK_RC2 -eq 0 ]; then
    echo -e "${GRN}[✓] Re-validation passed cleanly.${RST}"
    exit 0
  else
    echo -e "${YLW}[!] Re-validation still reports issues. See sdk_errors.txt${RST}"
    exit $SDK_RC2
  fi
else
  if [ $SDK_RC -ne 0 ]; then
    echo -e "${YLW}[!] demisto-sdk validate failed initially. Consider running with --revalidate to confirm fixes.${RST}"
    exit $SDK_RC
  fi
  exit 0
fi
