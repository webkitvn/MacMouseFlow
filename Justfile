set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

frontier:
    python3 scripts/next_work.py frontier

next:
    python3 scripts/next_work.py next

fmt:
    cargo fmt --all

build:
    cargo build --workspace --locked

check:
    python3 scripts/verify_toolchain.py
    python3 -m py_compile scripts/next_work.py scripts/verify_toolchain.py tests/test_next_work.py tests/test_repository_contract.py
    cargo fmt --all -- --check
    cargo clippy --workspace --all-targets --locked -- -D warnings

test:
    python3 -m unittest discover -s tests -p 'test_*.py'
    cargo test --workspace --locked

ci: check test build

hooks-install:
    chmod +x .githooks/pre-commit .githooks/pre-push
    git config core.hooksPath .githooks
    @echo "Installed repository hooks from .githooks"

benchmark:
    @echo "NOT READY: strict reference-Mac latency benchmark belongs to a later execution slice" >&2
    @exit 2

smoke:
    @echo "NOT READY: live macOS/TCC/Accessibility/CGEventTap smoke belongs to a later execution slice" >&2
    @exit 2

trace-tail:
    @echo "NOT READY: structured runtime trace capability belongs to the observability execution slice" >&2
    @exit 2

trace-export run_id="":
    @echo "NOT READY: structured runtime trace export belongs to the observability execution slice" >&2
    @exit 2
