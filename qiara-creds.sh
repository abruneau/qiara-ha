#!/usr/bin/env bash
# Retrieve Qiara API accounts (Customer ID + token) and keypad codes from the hub.
# Usage: ./qiara-creds.sh <hub-host> [ssh-key]
set -euo pipefail

HUB="${1:?usage: qiara-creds.sh <hub-host> [ssh-key]}"
KEY="${2:-$HOME/.ssh/qiara_ed25519}"

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

# Pull the most recent config snapshot (fbxhome.xml.* are rotated backups).
ssh -i "$KEY" -o StrictHostKeyChecking=accept-new "root@$HUB" \
  'cat "$(ls -1t /data/fbxhome.xml.* 2>/dev/null | head -1)"' > "$tmp"

python3 - "$tmp" <<'PY'
import re, sys
xml = open(sys.argv[1], encoding="utf-8", errors="replace").read()
attrs = lambda tag: dict(re.findall(r'(\w+)="([^"]*)"', tag))

print("== API accounts ==")
print("   Use one account's cust_id as 'Customer ID' and token as 'Secret Key'.\n")
for m in re.finditer(r"<AuthToken[^>]*>", xml):
    a = attrs(m.group(0))
    if a.get("discarded") == "true":
        continue
    print(f"   {a.get('label','?'):24}  cust_id={a.get('cust_id','')}  token={a.get('token','')}")

print("\n== Keypad codes ==")
for m in re.finditer(r"<Code[^>]*>", xml):
    a = attrs(m.group(0))
    if a.get("valid") != "true":
        continue
    print(f"   {a.get('label','?'):24}  PIN={a.get('password','')}")
PY
