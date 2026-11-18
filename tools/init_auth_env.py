"""Add a JWT key to the local .env without changing database credentials."""
import re
import secrets
from pathlib import Path


def main():
    path = Path(".env")
    if not path.is_file():
        raise SystemExit("Create .env from .env.example first.")
    content = path.read_text(encoding="utf-8-sig")
    matches = list(re.finditer(r"(?m)^JWT_SECRET_KEY\s*=([^\r\n]*)", content))
    if len(matches) > 1:
        raise SystemExit("Duplicate JWT_SECRET_KEY entries: keep just one before continuing.")
    if matches and matches[0].group(1).strip().strip("\"'"):
        print("Existing JWT_SECRET_KEY kept unchanged.")
        return
    entry = "JWT_SECRET_KEY=" + secrets.token_hex(32)
    if matches:
        match = matches[0]
        content = content[:match.start()] + entry + content[match.end():]
    else:
        content = content.rstrip("\r\n") + "\n\n" + entry + "\n"
    path.write_text(content, encoding="utf-8")
    print("JWT_SECRET_KEY added to .env. Database settings unchanged. Secret not displayed.")


if __name__ == "__main__":
    main()
