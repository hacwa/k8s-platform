#!/usr/bin/env python3

import pathlib
import sys

if len(sys.argv) != 5:
    raise SystemExit(
        "usage: render-coturn.py TEMPLATE OUTPUT "
        "SECRET_FILE POD_IP"
    )

template_path = pathlib.Path(sys.argv[1])
output_path = pathlib.Path(sys.argv[2])
secret_path = pathlib.Path(sys.argv[3])
pod_ip = sys.argv[4].strip()

secret = secret_path.read_text().rstrip("\n")

if not secret:
    raise SystemExit("TURN shared secret is empty.")

if "\n" in secret or "\r" in secret:
    raise SystemExit("TURN shared secret contains a newline.")

if not pod_ip:
    raise SystemExit("Pod IP is empty.")

content = template_path.read_text()

replacements = {
    "__TURN_SHARED_SECRET__": secret,
    "__POD_IP__": pod_ip,
}

for token, replacement in replacements.items():
    count = content.count(token)

    if count == 0:
        raise SystemExit(
            f"Token {token} was not found in the template."
        )

    content = content.replace(token, replacement)

output_path.parent.mkdir(
    parents=True,
    exist_ok=True,
)

output_path.write_text(content)
