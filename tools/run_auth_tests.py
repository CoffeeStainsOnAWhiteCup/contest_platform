"""Install test dependencies in a disposable container and run the chosen suite."""
import os
import subprocess
import sys


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "unit"
    if mode not in {"unit", "postgres"}:
        raise SystemExit("Usage: python tools/run_auth_tests.py [unit|postgres]")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--index-url", "https://pypi.org/simple",
         "-r", "requirements-auth-test.txt"], check=True,
    )
    if mode == "postgres":
        os.environ["AUTH_TEST_DATABASE_URL"] = os.environ["DATABASE_URL"]
        target = "tests/auth_integration"
    else:
        target = "tests/auth_unit"
    raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", target, "-q", "-ra"]))


if __name__ == "__main__":
    main()
