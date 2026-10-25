"""Generate a physical-approval token for one named operator.

Prints the token once (give it to that operator only) and the SPATIALTWIN_OPERATORS entry that holds its
hash. The server never stores the token itself. Usage:

    .venv/bin/python tools/operator_token.py alice
"""
import hashlib
import re
import secrets
import sys

NAME = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


def make_entry(name: str, token: str) -> str:
    if not NAME.match(name):
        raise ValueError("Operator names use letters, digits, '.', '_' or '-' (1-64 characters).")
    return f"{name}:{hashlib.sha256(token.encode('utf-8')).hexdigest()}"


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__.strip())
        return 2
    token = secrets.token_urlsafe(32)
    entry = make_entry(argv[0], token)
    print(f"Token for {argv[0]} (shown once; store it securely): {token}")
    print(f"Add to SPATIALTWIN_OPERATORS (comma-separated with other entries): {entry}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
