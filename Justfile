set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

frontier:
    python3 scripts/next_work.py frontier

next:
    python3 scripts/next_work.py next

test:
    python3 -m unittest discover -s tests -p 'test_*.py'

check:
    python3 -m py_compile scripts/next_work.py tests/test_next_work.py

ci: check test

hooks-install:
    @echo "NOT READY: hooks are not implemented yet" >&2
    @exit 2

benchmark:
    @echo "NOT READY: reference-Mac benchmark is not implemented yet" >&2
    @exit 2

smoke:
    @echo "NOT READY: live-system smoke is not implemented yet" >&2
    @exit 2
