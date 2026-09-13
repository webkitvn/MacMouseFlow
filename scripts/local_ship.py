#!/usr/bin/env python3
"""Local macOS ship pipeline for MacMouseFlow (OpenSpec change issue-41-local-ship-pipeline).

Builds a self-contained, ad-hoc-signed local development artifact and exercises its
install / update / rollback / uninstall lifecycle. Lifecycle tooling owns only
`LocalShip/` under the app's own Application Support directory: it never reads,
parses, migrates, rewrites, deletes, or repairs runtime configuration. It only records
existence / byte length / SHA-256 evidence for whatever configuration document (real or
sentinel) is already present.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_ID = "io.github.webkitvn.macmouseflow"
APP_NAME = "MacMouseFlow.app"
EXECUTABLE_NAME = "macmouseflow"
LAUNCH_TIMEOUT_SECONDS = 5.0
CANDIDATE_OUT_DIR = ROOT / "target" / "local-ship" / "candidate"


def fail(code: str, message: str) -> "NoReturn":
    print(f"{code}: {message}", file=sys.stderr)
    raise SystemExit(2)


# --- Fixed local paths (design.md: "Fixed local paths and one rollback bundle") ---


def home() -> Path:
    return Path.home()


def active_app_path() -> Path:
    return home() / "Applications" / APP_NAME


def support_dir() -> Path:
    return home() / "Library" / "Application Support" / BUNDLE_ID


def local_ship_dir() -> Path:
    return support_dir() / "LocalShip"


def rollback_app_path() -> Path:
    return local_ship_dir() / "rollback" / APP_NAME


# Real runtime configuration is native-owned (ADR 0004) and outside this pipeline's
# control; the pipeline only ever reads existence/length/hash, never contents.
def config_path() -> Path:
    return support_dir() / "configuration.json"


# Opaque sentinel used only when real configuration is absent, kept outside LocalShip/
# in the app-owned Application Support directory (design.md: "Configuration remains
# opaque and untouched").
def sentinel_path() -> Path:
    return support_dir() / "local-ship-config-sentinel.bin"


SENTINEL_MAGIC = b"MMF-LOCAL-SHIP-CONFIG-SENTINEL-V1\n"


# --- Hashing / evidence ---


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass
class ConfigEvidence:
    path: str
    is_sentinel: bool
    exists: bool
    byte_length: Optional[int]
    sha256: Optional[str]


def capture_config_evidence() -> ConfigEvidence:
    """Record existence/length/SHA-256 for the real config, or an opaque sentinel.

    Never opens the real configuration document for anything but a byte-length and
    digest read; never interprets its contents.
    """
    real = config_path()
    if real.exists():
        data_len = real.stat().st_size
        return ConfigEvidence(str(real), False, True, data_len, sha256_file(real))

    sentinel = sentinel_path()
    if not sentinel.exists():
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.write_bytes(SENTINEL_MAGIC)
    data_len = sentinel.stat().st_size
    return ConfigEvidence(str(sentinel), True, True, data_len, sha256_file(sentinel))


def assert_config_unchanged(before: ConfigEvidence, after: ConfigEvidence) -> None:
    if before.path != after.path or before.byte_length != after.byte_length or before.sha256 != after.sha256:
        fail(
            "CONFIG_MUTATED",
            f"runtime configuration evidence changed: before={before} after={after}",
        )


# --- Bundle identity / signature / launch-probe validation ---


@dataclass
class BundleValidation:
    ok: bool
    reason: str = ""


def _codesign(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["codesign", *args], text=True, capture_output=True, check=False)


def _codesign_display(bundle: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["codesign", "-dvvv", str(bundle)], text=True, capture_output=True, check=False)


# `codesign -dvvv` reports `flags=0x2(adhoc)` and `Signature=adhoc` only for an
# ad-hoc-signed (`codesign --sign -`) item; a real Developer ID or other identity
# reports a certificate chain there instead and must be rejected (locked exclusion:
# ad-hoc only, no Developer ID).
_AD_HOC_FLAG_PATTERN = re.compile(r"flags=0x[0-9a-fA-F]+\(adhoc\)")


def verify_ad_hoc_signature(bundle: Path) -> BundleValidation:
    """Require strict signature verification AND that the signature is specifically
    ad-hoc; retains strict codesign validation while explicitly excluding any real
    signing identity."""
    verify = _codesign("--verify", "--deep", "--strict", str(bundle))
    if verify.returncode != 0:
        return BundleValidation(False, f"ad-hoc signature verification failed: {verify.stderr.strip()}")

    display = _codesign_display(bundle)
    signing_info = display.stderr
    if not _AD_HOC_FLAG_PATTERN.search(signing_info) or "Signature=adhoc" not in signing_info:
        return BundleValidation(False, f"signature is not ad-hoc: {signing_info.strip()}")

    return BundleValidation(True)


def validate_static_identity(bundle: Path) -> BundleValidation:
    """Validate bundle ID, expected executable, and ad-hoc signature without executing
    anything. Used for a new candidate before it is ever committed to the canonical
    active path; the candidate's own launch behavior is proven only after that
    commit, at the canonical path (see `install`)."""
    if not bundle.is_dir():
        return BundleValidation(False, f"not a bundle directory: {bundle}")

    info_plist = bundle / "Contents" / "Info.plist"
    if not info_plist.is_file():
        return BundleValidation(False, "missing Contents/Info.plist")
    try:
        with info_plist.open("rb") as handle:
            plist = plistlib.load(handle)
    except Exception as exc:  # malformed plist
        return BundleValidation(False, f"malformed Info.plist: {exc}")

    if plist.get("CFBundleIdentifier") != BUNDLE_ID:
        return BundleValidation(False, f"unexpected bundle id: {plist.get('CFBundleIdentifier')!r}")
    if plist.get("CFBundleExecutable") != EXECUTABLE_NAME:
        return BundleValidation(False, f"unexpected bundle executable: {plist.get('CFBundleExecutable')!r}")

    executable = bundle / "Contents" / "MacOS" / EXECUTABLE_NAME
    if not executable.is_file():
        return BundleValidation(False, f"missing expected executable: {executable}")

    return verify_ad_hoc_signature(bundle)


def validate_bundle_identity(bundle: Path) -> BundleValidation:
    """Validate bundle ID, expected executable, ad-hoc signature, and launch probe
    before any mutation. Any foreign or malformed bundle content aborts without
    mutation (design.md decision "Fixed local paths and one rollback bundle"). Used
    for pre-existing active/rollback content, where the launch-probe check is exactly
    what proves it is still safe to touch.
    """
    static_validation = validate_static_identity(bundle)
    if not static_validation.ok:
        return static_validation

    executable = bundle / "Contents" / "MacOS" / EXECUTABLE_NAME
    probe = guarded_launch_probe(executable)
    if not probe.ok:
        return BundleValidation(False, f"launch probe failed: {probe.reason}")

    return BundleValidation(True)


def launch_probe(executable: Path) -> BundleValidation:
    """Execute the installed main executable; success is exit 0 within 5s.

    A resident process is not required (design.md: "M0 launch probe").
    """
    try:
        result = subprocess.run(
            [str(executable)],
            timeout=LAUNCH_TIMEOUT_SECONDS,
            capture_output=True,
        )
    except subprocess.TimeoutExpired:
        return BundleValidation(False, "did not exit within 5 seconds")
    except OSError as exc:
        return BundleValidation(False, f"dynamic-loader/exec failure: {exc}")

    if result.returncode < 0:
        return BundleValidation(False, f"terminated by signal {-result.returncode}")
    if result.returncode != 0:
        return BundleValidation(False, f"nonzero exit status {result.returncode}")
    return BundleValidation(True)


def guarded_launch_probe(executable: Path) -> BundleValidation:
    """Capture runtime-configuration evidence immediately before and after every
    candidate launch probe and verify it is unchanged before any caller acts on the
    probe result with a filesystem mutation. A probe that leaves an observable trace
    on runtime configuration is an integrity violation, not an expected failure mode,
    so it hard-stops rather than returning a structured result."""
    before = capture_config_evidence()
    result = launch_probe(executable)
    after = capture_config_evidence()
    assert_config_unchanged(before, after)
    return result


def validate_rollback_content(bundle: Path) -> BundleValidation:
    """Unexpected or malformed rollback content aborts without mutation."""
    return validate_bundle_identity(bundle)


# --- Candidate build (task 1.1 / 1.2) ---


def _run(cmd: list[str], cwd: Optional[Path] = None, env: Optional[dict] = None) -> None:
    print(f"+ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env)
    if result.returncode != 0:
        fail("BUILD_STEP_FAILED", f"command failed ({result.returncode}): {' '.join(cmd)}")


def build_candidate(profile: str = "release") -> Path:
    """Build a self-contained, ad-hoc-signed .app; prove static-linkage self-containment.

    Returns the path to the verified candidate bundle inside target/local-ship/candidate/.
    """
    import os

    _run(["cargo", "build", "-p", "pointer-input-ffi", f"--{profile}", "--locked"], cwd=ROOT)

    env = dict(os.environ)
    env["MMF_FFI_PROFILE"] = profile
    env["MMF_FFI_LINKAGE"] = "static"
    _run(
        ["swift", "build", "-c", profile, "--package-path", "macos", "--product", EXECUTABLE_NAME],
        cwd=ROOT,
        env=env,
    )

    built_executable = ROOT / "macos" / ".build" / profile / EXECUTABLE_NAME
    if not built_executable.is_file():
        fail("BUILD_STEP_FAILED", f"expected built executable missing: {built_executable}")

    if CANDIDATE_OUT_DIR.exists():
        shutil.rmtree(CANDIDATE_OUT_DIR)
    CANDIDATE_OUT_DIR.mkdir(parents=True, exist_ok=True)
    bundle = CANDIDATE_OUT_DIR / APP_NAME
    macos_dir = bundle / "Contents" / "MacOS"
    macos_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(built_executable, macos_dir / EXECUTABLE_NAME)
    (bundle / "Contents" / "Info.plist").write_bytes(_render_info_plist())

    _run(["codesign", "--sign", "-", "--force", "--deep", str(bundle)])
    verify = _codesign("--verify", "--deep", "--strict", str(bundle))
    if verify.returncode != 0:
        fail("SIGNATURE_VERIFICATION_FAILED", verify.stderr.strip())

    prove_self_contained(bundle)
    return bundle


def _render_info_plist() -> bytes:
    return plistlib.dumps(
        {
            "CFBundleIdentifier": BUNDLE_ID,
            "CFBundleExecutable": EXECUTABLE_NAME,
            "CFBundleName": "MacMouseFlow",
            "CFBundlePackageType": "APPL",
            "CFBundleShortVersionString": "0.0.0-local",
            "CFBundleVersion": "1",
            "LSMinimumSystemVersion": "14.0",
        }
    )


def prove_self_contained(bundle: Path) -> None:
    """Relocate the built executable outside the checkout and prove it runs with no
    dependency on the checkout or target/ (design.md: "Canonical build and
    self-containment proof")."""
    executable = bundle / "Contents" / "MacOS" / EXECUTABLE_NAME
    otool = subprocess.run(["otool", "-L", str(executable)], text=True, capture_output=True, check=False)
    if otool.returncode != 0:
        fail("SELF_CONTAINMENT_CHECK_FAILED", otool.stderr.strip())
    # First line is the inspected file's own path (always inside the checkout while
    # building); only the dependency lines that follow matter for self-containment.
    dependency_lines = otool.stdout.splitlines()[1:]
    if any(str(ROOT) in line for line in dependency_lines):
        fail(
            "SELF_CONTAINMENT_CHECK_FAILED",
            f"executable still depends on the checkout:\n{otool.stdout}",
        )

    with tempfile.TemporaryDirectory(prefix="mmf-local-ship-") as tmp:
        relocated = Path(tmp) / EXECUTABLE_NAME
        shutil.copy2(executable, relocated)
        probe = guarded_launch_probe(relocated)
        if not probe.ok:
            fail("SELF_CONTAINMENT_CHECK_FAILED", f"relocated executable failed launch probe: {probe.reason}")


# --- Transactional install / update / rollback / uninstall (task 2.1-2.3) ---


@dataclass
class LifecycleResult:
    action: str
    ok: bool
    reason: str = ""
    config_before: Optional[dict] = None
    config_after: Optional[dict] = None
    # Set only when a rollback double-failure (commit move AND automatic
    # restoration move both fail) leaves the backup as the sole recoverable copy
    # of the prior active bundle. Callers must treat its presence as "active is
    # NOT confirmed preserved; recover manually from this path."
    preserved_backup_path: Optional[str] = None


def install(candidate: Path) -> LifecycleResult:
    """Install/update `candidate` as the active bundle.

    Validates any pre-existing active and rollback content before mutation (aborting
    without mutation if either is foreign or malformed), retains the prior known-good
    bundle as the single rollback bundle, installs the candidate at the canonical
    active path, and only then runs the launch probe *at that canonical path* (not a
    staging copy). A canonical-path launch-probe failure or a filesystem error while
    replacing the canonical active path automatically restores the retained known-good
    bundle and returns a structured failure; it never leaves an unmentioned failure or
    a silently broken active bundle in place.
    """
    config_before = capture_config_evidence()

    candidate_validation = validate_static_identity(candidate)
    if not candidate_validation.ok:
        config_after = capture_config_evidence()
        assert_config_unchanged(config_before, config_after)
        return LifecycleResult(
            "install",
            False,
            f"candidate invalid: {candidate_validation.reason}",
            asdict(config_before),
            asdict(config_after),
        )

    active = active_app_path()
    rb = rollback_app_path()

    if rb.exists():
        rollback_validation = validate_rollback_content(rb)
        if not rollback_validation.ok:
            config_after = capture_config_evidence()
            assert_config_unchanged(config_before, config_after)
            return LifecycleResult(
                "install",
                False,
                f"aborted: existing rollback bundle is malformed: {rollback_validation.reason}",
                asdict(config_before),
                asdict(config_after),
            )

    had_active = active.exists()
    if had_active:
        active_validation = validate_bundle_identity(active)
        if not active_validation.ok:
            config_after = capture_config_evidence()
            assert_config_unchanged(config_before, config_after)
            return LifecycleResult(
                "install",
                False,
                f"aborted: existing active bundle is foreign or malformed: {active_validation.reason}",
                asdict(config_before),
                asdict(config_after),
            )

    # Retain known-good: move the current active bundle into the rollback slot
    # *before* the canonical active path is mutated, so a failure below always has
    # something correct to restore.
    moved_prior_active = False
    if had_active:
        try:
            rb.parent.mkdir(parents=True, exist_ok=True)
            if rb.exists():
                shutil.rmtree(rb)
            shutil.move(str(active), str(rb))
            moved_prior_active = True
        except OSError as exc:
            config_after = capture_config_evidence()
            assert_config_unchanged(config_before, config_after)
            return LifecycleResult(
                "install",
                False,
                f"filesystem error retaining known-good bundle, active left untouched: {exc}",
                asdict(config_before),
                asdict(config_after),
            )

    try:
        active.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(candidate, active)
    except OSError as exc:
        restore_note = _restore_known_good(moved_prior_active, rb, active)
        config_after = capture_config_evidence()
        assert_config_unchanged(config_before, config_after)
        return LifecycleResult(
            "install",
            False,
            f"filesystem error installing candidate at canonical active path: {exc}; {restore_note}",
            asdict(config_before),
            asdict(config_after),
        )

    # Only now, at the real canonical active path (never a staging proxy), do we
    # prove the candidate actually launches.
    try:
        probe = guarded_launch_probe(active / "Contents" / "MacOS" / EXECUTABLE_NAME)
    except SystemExit:
        # guarded_launch_probe hard-stops on a config-integrity violation. The
        # candidate is already committed to the canonical path at this point, so a
        # crash here would leave it in place uninvestigated; treat it exactly like a
        # failed probe instead and restore/report. Do not re-assert unchanged config
        # here - the violation is why we are in this branch.
        restore_note = _restore_known_good(moved_prior_active, rb, active)
        config_after = capture_config_evidence()
        return LifecycleResult(
            "install",
            False,
            f"canonical-path launch probe corrupted configuration evidence (see CONFIG_MUTATED above); {restore_note}",
            asdict(config_before),
            asdict(config_after),
        )

    if not probe.ok:
        restore_note = _restore_known_good(moved_prior_active, rb, active)
        config_after = capture_config_evidence()
        assert_config_unchanged(config_before, config_after)
        return LifecycleResult(
            "install",
            False,
            f"canonical-path launch probe failed: {probe.reason}; {restore_note}",
            asdict(config_before),
            asdict(config_after),
        )

    config_after = capture_config_evidence()
    assert_config_unchanged(config_before, config_after)
    return LifecycleResult("install", True, "", asdict(config_before), asdict(config_after))


def _restore_known_good(moved_prior_active: bool, rb: Path, active: Path) -> str:
    """Best-effort automatic restoration of the canonical active path after a failed
    install. A restoration failure is reported in the returned note, never silently
    swallowed."""
    try:
        if active.exists():
            shutil.rmtree(active)
    except OSError as exc:
        return f"AUTOMATIC RESTORATION FAILED while clearing the failed candidate: {exc}"

    if not moved_prior_active:
        return "no prior active bundle existed; canonical active path left empty"

    if not rb.exists():
        return "AUTOMATIC RESTORATION FAILED: rollback bundle unexpectedly missing"

    try:
        shutil.copytree(rb, active)
    except OSError as exc:
        return f"AUTOMATIC RESTORATION FAILED: {exc}"

    return "automatically restored the known-good bundle to the canonical active path"


def rollback() -> LifecycleResult:
    """Restore the single known-good rollback bundle over the active bundle.

    Never deletes the active bundle before a working replacement is ready: the
    rollback bundle is copied into a staging location first, and only a working
    staged copy is swapped in for active (moving the existing active bundle to a
    backup slot rather than deleting it). Any staging or swap failure leaves the
    original active bundle exactly as it was, EXCEPT in the double-failure case
    where the commit move and the automatic restoration move both fail: `active`
    is then genuinely missing, and the backup is preserved undeleted at a
    documented path (`LifecycleResult.preserved_backup_path`) instead of being
    treated as disposable, so no recoverable copy of the prior known-good bundle
    is ever lost.
    """
    config_before = capture_config_evidence()
    rb = rollback_app_path()
    if not rb.exists():
        config_after = capture_config_evidence()
        assert_config_unchanged(config_before, config_after)
        return LifecycleResult(
            "rollback", False, "no rollback bundle available", asdict(config_before), asdict(config_after)
        )

    rb_validation = validate_rollback_content(rb)
    if not rb_validation.ok:
        config_after = capture_config_evidence()
        assert_config_unchanged(config_before, config_after)
        return LifecycleResult(
            "rollback",
            False,
            f"rollback bundle is malformed: {rb_validation.reason}",
            asdict(config_before),
            asdict(config_after),
        )

    active = active_app_path()
    staged = active.parent / f".{APP_NAME}.rollback-staging"
    backup = active.parent / f".{APP_NAME}.rollback-backup"

    try:
        if staged.exists():
            shutil.rmtree(staged)
        active.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(rb, staged)
    except OSError as exc:
        shutil.rmtree(staged, ignore_errors=True)
        config_after = capture_config_evidence()
        assert_config_unchanged(config_before, config_after)
        return LifecycleResult(
            "rollback",
            False,
            f"filesystem error staging rollback bundle, active left untouched: {exc}",
            asdict(config_before),
            asdict(config_after),
        )

    active_existed = active.exists()
    replace_error: Optional[str] = None
    # Set only in the double-failure case below (commit move fails AND the
    # automatic restoration move also fails), when `backup` is the sole
    # remaining recoverable copy of the prior active bundle and must survive
    # this call rather than being cleaned up.
    unrecoverable_backup_path: Optional[str] = None
    try:
        if backup.exists():
            shutil.rmtree(backup)
        if active_existed:
            # Move (not delete) the current active bundle aside; it is only ever
            # discarded once the staged replacement has been committed successfully.
            shutil.move(str(active), str(backup))
        shutil.move(str(staged), str(active))
    except OSError as commit_exc:
        if active_existed and not active.exists() and backup.exists():
            try:
                shutil.move(str(backup), str(active))
            except OSError as restore_exc:
                # Double failure: neither the commit move nor the automatic
                # restoration succeeded. `active` is genuinely missing right now
                # -- this must never be reported as "active preserved". The
                # backup is the only remaining recoverable copy of the prior
                # known-good bundle and must never be deleted here; leave it at
                # its documented path for manual recovery and report that path.
                unrecoverable_backup_path = str(backup)
                replace_error = (
                    f"commit failed ({commit_exc}) and automatic restoration also failed "
                    f"({restore_exc}); active is MISSING, not preserved; the last recoverable "
                    f"known-good bundle is intentionally left at {backup} for manual recovery"
                )
            else:
                replace_error = (
                    f"commit failed ({commit_exc}); automatically restored active from the backup copy"
                )
        else:
            replace_error = str(commit_exc)
    finally:
        shutil.rmtree(staged, ignore_errors=True)
        if unrecoverable_backup_path is None:
            shutil.rmtree(backup, ignore_errors=True)

    if replace_error is not None:
        config_after = capture_config_evidence()
        assert_config_unchanged(config_before, config_after)
        return LifecycleResult(
            "rollback",
            False,
            f"filesystem error replacing active with staged rollback bundle: {replace_error}",
            asdict(config_before),
            asdict(config_after),
            unrecoverable_backup_path,
        )

    config_after = capture_config_evidence()
    assert_config_unchanged(config_before, config_after)
    return LifecycleResult("rollback", True, "", asdict(config_before), asdict(config_after))


def uninstall() -> LifecycleResult:
    """Remove the active artifact; report remaining documented local state.

    Runtime configuration is never touched.
    """
    config_before = capture_config_evidence()
    active = active_app_path()
    removed = active.exists()
    if removed:
        shutil.rmtree(active)

    config_after = capture_config_evidence()
    assert_config_unchanged(config_before, config_after)

    remaining = {
        "active_removed": removed,
        "rollback_bundle_present": rollback_app_path().exists(),
        "local_ship_dir_present": local_ship_dir().exists(),
        "support_dir_present": support_dir().exists(),
    }
    return LifecycleResult(
        "uninstall", True, json.dumps(remaining), asdict(config_before), asdict(config_after)
    )


# --- Same-artifact transport verification (task 3.1) ---


def package_for_transport(bundle: Path, out_zip: Path) -> str:
    """Zip `bundle` for transport (preserving code-signing metadata) and return its
    SHA-256 digest. The zip, not the bundle, is the artifact whose digest travels with
    it; the receiving host never rebuilds from source."""
    out_zip.parent.mkdir(parents=True, exist_ok=True)
    if out_zip.exists():
        out_zip.unlink()
    _run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(bundle), str(out_zip)])
    return sha256_file(out_zip)


def verify_transport(zip_path: Path, expected_sha256: str, extract_dir: Path) -> BundleValidation:
    """Verify a transported zip's digest, then unpack and re-verify bundle identity and
    ad-hoc signature without any rebuild."""
    actual = sha256_file(zip_path)
    if actual != expected_sha256:
        return BundleValidation(False, f"SHA-256 mismatch after transport: expected {expected_sha256}, got {actual}")

    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)
    _run(["ditto", "-x", "-k", str(zip_path), str(extract_dir)])
    return validate_bundle_identity(extract_dir / APP_NAME)


# --- CLI ---


def _print_result(result: LifecycleResult) -> None:
    print(json.dumps(asdict(result), indent=2))
    if not result.ok:
        raise SystemExit(1)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    build_parser = sub.add_parser("build", help="build, sign, and self-containment-prove a candidate")
    build_parser.add_argument("--profile", default="release")

    install_parser = sub.add_parser("install", help="transactionally install/update the active bundle")
    install_parser.add_argument("candidate", type=Path)

    sub.add_parser("rollback", help="restore the known-good rollback bundle")
    sub.add_parser("uninstall", help="remove the active bundle")
    sub.add_parser(
        "verify-active",
        help="validate the current active bundle's identity, ad-hoc signature, and launch probe",
    )

    package_parser = sub.add_parser(
        "package-for-transport", help="zip a candidate bundle and print its SHA-256 digest"
    )
    package_parser.add_argument("bundle", type=Path)
    package_parser.add_argument("out_zip", type=Path)

    verify_parser = sub.add_parser(
        "verify-transport",
        help="verify a transported zip's SHA-256 and ad-hoc signature, then unpack it (no rebuild)",
    )
    verify_parser.add_argument("zip_path", type=Path)
    verify_parser.add_argument("expected_sha256")
    verify_parser.add_argument("extract_dir", type=Path)

    args = parser.parse_args(argv)

    if args.command == "build":
        bundle = build_candidate(profile=args.profile)
        print(json.dumps({"bundle": str(bundle), "sha256": sha256_file(bundle / "Contents" / "MacOS" / EXECUTABLE_NAME)}))
        return 0
    if args.command == "install":
        _print_result(install(args.candidate))
        return 0
    if args.command == "rollback":
        _print_result(rollback())
        return 0
    if args.command == "uninstall":
        _print_result(uninstall())
        return 0
    if args.command == "verify-active":
        result = validate_bundle_identity(active_app_path())
        print(json.dumps(asdict(result)))
        if not result.ok:
            raise SystemExit(1)
        return 0
    if args.command == "package-for-transport":
        digest = package_for_transport(args.bundle, args.out_zip)
        print(json.dumps({"zip": str(args.out_zip), "sha256": digest}))
        return 0
    if args.command == "verify-transport":
        result = verify_transport(args.zip_path, args.expected_sha256, args.extract_dir)
        print(json.dumps(asdict(result)))
        if not result.ok:
            raise SystemExit(1)
        return 0

    fail("UNKNOWN_COMMAND", str(args.command))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
