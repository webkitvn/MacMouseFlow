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
    python3 scripts/guardrail_registry.py --check
    python3 -m py_compile scripts/next_work.py scripts/verify_toolchain.py scripts/guardrail_registry.py tests/test_next_work.py tests/test_repository_contract.py tests/test_guardrail_registry.py
    cargo fmt --all -- --check
    cargo clippy --workspace --all-targets --locked -- -D warnings

test:
    python3 -m unittest discover -s tests -p 'test_*.py'
    cargo test --workspace --locked
    cargo build -p pointer-input-ffi --locked
    cc -std=c11 -Wall -Wextra -Werror -Irust/ffi/include rust/ffi/tests/abi_contract.c -Ltarget/debug -lpointer_input_ffi -Wl,-rpath,"$PWD/target/debug" -o target/abi_contract
    target/abi_contract
    swift test --package-path macos

ci: check test build

hooks-install:
    chmod +x .githooks/pre-commit .githooks/pre-push
    git config core.hooksPath .githooks
    @echo "Installed repository hooks from .githooks"

benchmark:
    cargo build -p pointer-input-ffi --locked
    swift run --package-path macos benchmark

smoke:
    cargo build -p pointer-input-ffi --locked
    swift run --package-path macos smoke

macos14-behavior:
    cargo build -p pointer-input-ffi --locked
    swift run --package-path macos coherence-check

trace-tail:
    @echo "NOT READY: structured runtime trace capability belongs to the observability execution slice" >&2
    @exit 2

trace-export run_id="":
    @echo "NOT READY: structured runtime trace export belongs to the observability execution slice" >&2
    @exit 2
