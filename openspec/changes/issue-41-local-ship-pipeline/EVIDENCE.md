# Evidence mapping — issue-41-local-ship-pipeline

Worker-owned evidence artifact for task 4.3. Maps every acceptance requirement in
`specs/local-macos-ship-pipeline/spec.md` to its macOS 26 (reference Mac) evidence
and, separately, its macOS 14 hosted-compatibility evidence. macOS 26 evidence never
substitutes for the macOS 14 row (design.md decision "Two-host lifecycle evidence").

Baseline commit: `cabf05d986bdf9fe95e8ae477495ccd2eea15046`. Reference Mac: macOS
26.6.2 (this host). Last refreshed against the current worker diff (post
CHANGES_REQUESTED fixes: canonical-path-commit-then-probe install, SystemExit-safe
restoration, stage-then-swap rollback).

## Requirement: Produce a verified local development artifact

| Scenario | macOS 26 evidence | macOS 14 hosted-compatibility evidence |
|---|---|---|
| Clean checkout produces an eligible artifact | `just local-build` run from an isolated clean-checkout copy (rsync excluding `.git`/`target`/`macos/.build`): `just ci` passed, static-linkage self-containment proven (`otool -L` on the built executable shows only system/Swift-runtime dylibs, zero references to the checkout or `target/`; relocated-to-`/tmp` copy exits 0), candidate ad-hoc signed and `codesign --verify --deep --strict` + `flags=0x2(adhoc)`/`Signature=adhoc` both confirmed. | **NOT PROVEN** — `local-ship-candidate` job (`.github/workflows/ci.yml`) has never executed on GitHub's hosted `macos-26`/`macos-14` infrastructure; no push or `workflow_dispatch` occurred this session. |
| Verification or signing fails | `verify_ad_hoc_signature`/`validate_static_identity` unit-tested (`tests/test_local_ship.py::BundleValidationTests`) to reject non-ad-hoc signatures, missing/malformed `Info.plist`, wrong bundle ID/executable. | **NOT PROVEN** — same job never run remotely. |

## Requirement: Exercise the local artifact lifecycle

| Scenario | macOS 26 evidence | macOS 14 hosted-compatibility evidence |
|---|---|---|
| Install and launch | Real install to `~/Applications/MacMouseFlow.app`: `codesign -dv --verify` → "valid on disk / satisfies its Designated Requirement"; timed launch probe exit 0 in ~7ms (< 5s). | **NOT PROVEN** — `macos14-lifecycle` job never run remotely. |
| Update and rollback | Real second install created exactly one valid, signed rollback bundle; explicit `rollback` command (stage-then-swap, never deletes active before a ready replacement — `tests/test_local_ship.py::test_rollback_filesystem_error_while_{staging,replacing}_preserves_active`) restored it; verified with `verify-active`. | **NOT PROVEN**. |
| Uninstall | Real `uninstall` removed the active bundle; reported remaining state `{"active_removed": true, "rollback_bundle_present": true, "local_ship_dir_present": true, "support_dir_present": true}`; config sentinel byte-identical throughout. | **NOT PROVEN**. |

## Requirement: Prove same-artifact lifecycle compatibility on hosted macOS 14

| Scenario | macOS 26 evidence | macOS 14 hosted-compatibility evidence |
|---|---|---|
| Same artifact transported and verified | `package_for_transport`/`verify_transport` round-trip unit-tested locally via `ditto` + SHA-256 (`tests/test_local_ship.py::TransportVerificationTests`); mechanism proven correct. | **NOT PROVEN** — this is the acceptance row itself; it can only be satisfied by an observed run of `local-ship-candidate` → `macos14-lifecycle` on GitHub's real hosted runners, which has not occurred. |
| Hosted macOS 14 lifecycle compatibility passes | N/A (macOS 26 evidence is not a substitute for this row). | **NOT PROVEN**. |
| Hosted macOS 14 unavailable or incompatible | N/A. | This row's actual status **for this change**: NOT PROVEN because no remote run was authorized/attempted, not because the runner was observed unavailable. Per design.md/tasks.md 3.3, this blocks archive and returns to Issue #41 for a lead decision. |

## Requirement: Preserve failure safety and pre-v1 boundaries

| Scenario | macOS 26 evidence | macOS 14 hosted-compatibility evidence |
|---|---|---|
| Failed replacement preserves state | Real genuine controlled failed update: an ad-hoc-signed, identity-valid candidate with `exit code 9` was committed to the canonical active path, then failed its canonical-path probe → `"canonical-path launch probe failed: nonzero exit status 9; automatically restored the known-good bundle to the canonical active path"`; active SHA-256 confirmed restored; config sentinel unchanged. Plus unit tests for a config-integrity-violation `SystemExit` surfacing *after* canonical commit (`test_config_mutation_after_canonical_replacement_restores_known_good`, `test_config_mutation_after_first_install_replacement_leaves_active_empty`) and filesystem errors during install/rollback (`test_filesystem_error_installing_candidate_is_reported_and_restorable`, `test_rollback_filesystem_error_while_{staging,replacing}_preserves_active`), all confirming active is restored/preserved and never left deleted-but-not-replaced. `rollback()`'s single-failure paths (commit move fails and the automatic restoration succeeds, or the initial move-aside fails) both leave `active` genuinely intact or restored — evidenced by the two tests above. | **NOT PROVEN** — the workflow's dedicated "genuine controlled failed-update rollback" step exists in `.github/workflows/ci.yml` but has never executed remotely. |
| Rollback double failure (commit move AND automatic restoration both fail) never destroys the last recoverable copy | Fixed and evidenced this round: `rollback()` no longer unconditionally deletes the backup slot in its cleanup path. When both the staged→active commit move and the backup→active restoration move fail, the backup directory is left on disk, undeleted, at a documented path (`.{APP_NAME}.rollback-backup` under `active.parent`), and `LifecycleResult.preserved_backup_path` reports that exact path. The returned `reason` states `"active is MISSING, not preserved"` and never claims restoration in this branch. Regression test `test_rollback_double_failure_preserves_backup_and_reports_it_honestly` (`tests/test_local_ship.py`) fault-injects both moves failing and asserts: the backup still exists and is a valid bundle (`validate_bundle_identity(backup).ok`), `active` does not exist, `result.ok is False`, `result.preserved_backup_path == str(backup)`, the reason contains `"MISSING, not preserved"` and not `"automatically restored"`, and the config sentinel is unchanged. Prior to this fix the `finally` block called `shutil.rmtree(backup, ignore_errors=True)` unconditionally, which would have destroyed this last recoverable copy in exactly this scenario — this row previously overclaimed general rollback failure-safety without covering that case; it is now fixed and evidenced. | N/A — filesystem fault injection of this kind is not meaningfully distinct on hosted macOS 14 from macOS 26; this row is proven by the local unit test regardless of host, and is not part of the same-artifact lifecycle-compatibility acceptance criterion. |
| Foreign or malformed copy aborts | Real test: a foreign-bundle-ID active copy caused install to abort with zero mutation (`tests/test_local_ship.py::test_install_aborts_without_mutation_when_active_is_foreign`); malformed rollback content rejected without mutation. | **NOT PROVEN**. |
| Unsupported distribution request | No Developer ID, notarization, public distribution, quarantine removal, or new helper/daemon/process was added anywhere in this diff (verified by review of `scripts/local_ship.py`, `.github/workflows/ci.yml`, `Justfile`, `Package.swift`, `Cargo.toml`). | N/A — this is a design-time exclusion, not a runtime scenario requiring hosted evidence. |

## Summary

- **macOS 26 reference-Mac row: fully evidenced** for every requirement above, using genuine real-machine installs/updates/failures/rollbacks/uninstalls plus targeted unit tests for fault-injection scenarios that are impractical to trigger organically on real hardware every run.
- **macOS 14 hosted-compatibility row: NOT PROVEN for every requirement.** No commit was pushed and no `workflow_dispatch` was triggered this session (worker scope prohibits committing/pushing). The CI wiring (`local-ship-candidate`, `macos14-lifecycle` jobs) is implemented and unit-tested at the mechanism level (transport SHA-256/signature verification, ad-hoc-only signature enforcement) but has no observed remote execution.
- Per design.md/tasks.md (task 3.3), this change **must not archive or close** until the macOS 14 row is observed to PASS on a real GitHub Actions run, or a lead decision explicitly accepts/updates this acceptance criterion. This file does not lower that bar; it only makes the current evidence state explicit and auditable.
