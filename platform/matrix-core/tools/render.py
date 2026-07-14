#!/usr/bin/env python3

import json
import pathlib
import sys

if len(sys.argv) < 3:
    raise SystemExit(
        "usage: render.py TEMPLATE OUTPUT [TOKEN:SECRET_PATH ...]"
    )

template_path = pathlib.Path(sys.argv[1])
output_path = pathlib.Path(sys.argv[2])
content = template_path.read_text()

for specification in sys.argv[3:]:
    token, secret_path = specification.split(":", 1)

    value = pathlib.Path(
        secret_path
    ).read_text().rstrip("\n")

    count = content.count(token)

    if count != 1:
        raise SystemExit(
            f"Token {token} appears {count} times in "
            f"{template_path}"
        )

    content = content.replace(
        token,
        json.dumps(value),
    )

output_path.parent.mkdir(
    parents=True,
    exist_ok=True,
)

output_path.write_text(content)
