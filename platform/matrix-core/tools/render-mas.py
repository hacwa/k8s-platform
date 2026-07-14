#!/usr/bin/env python3

import json
import pathlib
import sys
import urllib.parse

if len(sys.argv) != 7:
    raise SystemExit(
        "usage: render-mas.py TEMPLATE OUTPUT "
        "DATABASE_PASSWORD SHARED_SECRET "
        "KEYCLOAK_CLIENT_SECRET SECRETS_DIRECTORY"
    )

template_path = pathlib.Path(sys.argv[1])
output_path = pathlib.Path(sys.argv[2])
database_password_path = pathlib.Path(sys.argv[3])
shared_secret_path = pathlib.Path(sys.argv[4])
keycloak_secret_path = pathlib.Path(sys.argv[5])
secrets_directory = pathlib.Path(sys.argv[6])

database_password = database_password_path.read_text().rstrip("\n")
shared_secret = shared_secret_path.read_text().rstrip("\n")
keycloak_secret = keycloak_secret_path.read_text().rstrip("\n")

encoded_password = urllib.parse.quote(
    database_password,
    safe="",
)

database_uri = (
    "postgresql://mas:"
    + encoded_password
    + "@synapse-postgresql:5432/mas?sslmode=disable"
)

content = template_path.read_text()

replacements = {
    "__DATABASE_URI__": json.dumps(database_uri),
    "__MATRIX_SHARED_SECRET__": json.dumps(shared_secret),
    "__KEYCLOAK_CLIENT_SECRET__": json.dumps(keycloak_secret),
}

for token, replacement in replacements.items():
    count = content.count(token)

    if count != 1:
        raise SystemExit(
            f"{token}: expected one occurrence, found {count}"
        )

    content = content.replace(token, replacement)

output_path.parent.mkdir(
    parents=True,
    exist_ok=True,
)

secrets_directory.mkdir(
    parents=True,
    exist_ok=True,
)

output_path.write_text(content)
