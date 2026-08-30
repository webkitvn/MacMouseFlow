#!/usr/bin/env python3

import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
RUST_PIN = "1.98.0"
XCODE_PIN = "16.4"


def fail(message: str) -> None:
    print(f"TOOLCHAIN_MISMATCH: {message}", file=sys.stderr)
    raise SystemExit(2)


def run(*args: str) -> str:
    result = subprocess.run(args, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "command failed"
        fail(f"{' '.join(args)}: {detail}")
    return result.stdout.strip()


def verify_rust() -> None:
    pinned = (ROOT / "rust-toolchain.toml").read_text()
    if f'channel = "{RUST_PIN}"' not in pinned:
        fail(f"rust-toolchain.toml must pin Rust {RUST_PIN}")

    actual = run("rustc", "--version")
    match = re.match(r"rustc\s+(\d+\.\d+\.\d+)", actual)
    if not match or match.group(1) != RUST_PIN:
        fail(f"expected rustc {RUST_PIN}, found {actual}")
    print(f"Rust {RUST_PIN}")


def verify_xcode() -> None:
    pinned = (ROOT / ".xcode-version").read_text().strip()
    if pinned != XCODE_PIN:
        fail(f".xcode-version must pin Xcode {XCODE_PIN}")

    if sys.platform != "darwin":
        print(f"Xcode {XCODE_PIN} (pin validated; runtime check skipped off macOS)")
        return

    actual = run("xcodebuild", "-version")
    match = re.search(r"Xcode\s+(\d+\.\d+)", actual)
    if not match or match.group(1) != XCODE_PIN:
        fail(f"expected Xcode {XCODE_PIN}, found {actual.splitlines()[0] if actual else actual}")
    print(f"Xcode {XCODE_PIN}")


def main() -> int:
    verify_rust()
    verify_xcode()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
