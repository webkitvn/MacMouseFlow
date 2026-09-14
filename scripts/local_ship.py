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

# macOS 14+ on Apple Silicon (arm64) only through v1 (ADR-0006; PR #90 review comment,
# Issue #41). Explicit, not inferred from the build host's or a hosted CI runner's
# default target triple or OS-version label.
RUST_TARGET_TRIPLE = "aarch64-apple-darwin"
REQUIRED_EXECUTABLE_ARCH = "arm64"


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


# The single, pipeline-owned, documented path for the bounded terminal recovery
# bundle (design.md: "Bounded terminal recovery bundle on double filesystem
# failure"; lead decision, Issue #41). Populated only on a true double filesystem
# failure during a directory swap -- the commit move fails AND the automatic
# restoration move also fails -- and removed automatically by the next successful
# lifecycle action. This is not a second rollback slot or version history.
def terminal_recovery_path() -> Path:
    return local_ship_dir() / "terminal-recovery" / APP_NAME


# Other transient staging/backup slots used mid-operation by `install`/`rollback`;
# always disposable and normally cleaned up within the same call, but swept
# defensively (along with `terminal_recovery_path()`) on the next successful
# lifecycle action in case a prior call was interrupted before it could clean up.
_TRANSIENT_SLOT_SUFFIXES = (
    "rollback-staging",
    "rollback-backup",
    "rollback-incoming",
    "rollback-old",
    "rollback-restore-staging",
    "rollback-restore-backup",
)


@dataclass
class CleanupResult:
    ok: bool
    reason: str = ""


def _clear_pipeline_temp_state() -> CleanupResult:
    """Remove any leftover transient slot and verify the bounded terminal recovery
    bundle is actually gone.

    Called only once a lifecycle action is about to report success, so the terminal
    recovery bundle never persists past the next successful lifecycle action. The
    transient staging/backup slots are always-disposable mid-operation scratch space
    and are cleared best-effort. The terminal recovery bundle is different: it is the
    one documented, reported exception this pipeline makes to "exactly one rollback
    bundle" (design.md: "Bounded terminal recovery bundle on double filesystem
    failure"), so its removal is verified rather than assumed. A caller MUST NOT
    report unqualified lifecycle success while this reports failure.
    """
    for parent in (active_app_path().parent, rollback_app_path().parent):
        for suffix in _TRANSIENT_SLOT_SUFFIXES:
            candidate = parent / f".{APP_NAME}.{suffix}"
            if candidate.exists():
                shutil.rmtree(candidate, ignore_errors=True)

    recovery = terminal_recovery_path()
    recovery_root = recovery.parent
    if recovery_root.exists():
        shutil.rmtree(recovery_root, ignore_errors=True)
    if recovery.exists() or recovery_root.exists():
        return CleanupResult(
            False,
            f"the terminal recovery bundle at {recovery} could not be removed after a successful "
            f"lifecycle action; it remains on disk and must be treated as still-present recovery "
            f"state, not silently cleared",
        )
    return CleanupResult(True)


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


def assert_thin_arm64_executable(executable: Path) -> None:
    """Verify `executable` is a thin `arm64` Mach-O binary, never a Universal Binary or
    any other architecture (ADR-0006: macOS 14+ on Apple Silicon only through v1;
    PR #90 review comment, Issue #41). Aborts rather than accepting, translating, or
    silently widening to a non-arm64 artifact.
    """
    lipo = subprocess.run(["lipo", "-archs", str(executable)], text=True, capture_output=True, check=False)
    if lipo.returncode != 0:
        fail("ARCHITECTURE_CHECK_FAILED", f"could not inspect executable architecture: {lipo.stderr.strip()}")

    archs = lipo.stdout.split()
    if archs != [REQUIRED_EXECUTABLE_ARCH]:
        fail(
            "ARCHITECTURE_CHECK_FAILED",
            f"expected a thin {REQUIRED_EXECUTABLE_ARCH} executable, got architecture(s) {archs!r} for {executable}",
        )


def build_candidate(profile: str = "release") -> Path:
    """Build a self-contained, ad-hoc-signed .app; prove static-linkage self-containment.

    Returns the path to the verified candidate bundle inside target/local-ship/candidate/.
    """
    import os

    _run(
        ["cargo", "build", "-p", "pointer-input-ffi", f"--{profile}", "--locked", "--target", RUST_TARGET_TRIPLE],
        cwd=ROOT,
    )

    env = dict(os.environ)
    env["MMF_FFI_PROFILE"] = profile
    env["MMF_FFI_LINKAGE"] = "static"
    env["MMF_FFI_TARGET_TRIPLE"] = RUST_TARGET_TRIPLE
    _run(
        ["swift", "build", "-c", profile, "--package-path", "macos", "--product", EXECUTABLE_NAME],
        cwd=ROOT,
        env=env,
    )

    built_executable = ROOT / "macos" / ".build" / profile / EXECUTABLE_NAME
    if not built_executable.is_file():
        fail("BUILD_STEP_FAILED", f"expected built executable missing: {built_executable}")

    # Verify architecture before the executable is ever copied into the candidate
    # bundle or made eligible for signing (ADR-0006).
    assert_thin_arm64_executable(built_executable)

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
    # Set only when a true double filesystem failure (commit move AND automatic
    # restoration move both fail) leaves the canonical target genuinely missing and
    # the bundle that would otherwise be destroyed has been relocated to the bounded
    # terminal recovery bundle path (`terminal_recovery_path()`). Callers must treat
    # its presence as "the canonical target is NOT confirmed preserved; recover
    # manually from this path." This is never a second rollback slot: the recovery
    # bundle is removed automatically by the next successful lifecycle action.
    preserved_recovery_path: Optional[str] = None


@dataclass
class ReplaceResult:
    ok: bool
    reason: str = ""
    preserved_recovery_path: Optional[str] = None


def _replace_directory_content(source: Path, target: Path, backup: Path) -> ReplaceResult:
    """Replace `target`'s content with `source`'s content without ever deleting a
    pre-existing `target` before the replacement is confirmed safely swapped in.

    `target`, if present, is moved aside to `backup` first (never deleted outright);
    `source` is then moved into `target`'s place. This function does not delete
    `backup` (or a leftover `source`) on success -- callers own that cleanup, since
    some callers need `backup` to remain available until a further post-condition
    (e.g. a launch probe) passes before it is safe to discard.

    If moving `source` into `target` fails, an automatic restoration
    (`backup` -> `target`) is attempted. If that restoration also fails, `target` is
    genuinely missing right now: this is a true double filesystem failure
    (design.md: "Bounded terminal recovery bundle on double filesystem failure").
    The content that would otherwise be destroyed is relocated to the single,
    documented `terminal_recovery_path()` -- never left at the ad hoc `backup` path
    and never silently deleted. Callers MUST NOT report `target` as preserved when
    `preserved_recovery_path` is set.
    """
    target_existed = target.exists()
    try:
        if backup.exists():
            shutil.rmtree(backup)
        if target_existed:
            shutil.move(str(target), str(backup))
        shutil.move(str(source), str(target))
    except OSError as commit_exc:
        if target_existed and not target.exists() and backup.exists():
            try:
                shutil.move(str(backup), str(target))
            except OSError as restore_exc:
                recovery = terminal_recovery_path()
                try:
                    recovery.parent.mkdir(parents=True, exist_ok=True)
                    if recovery.exists():
                        shutil.rmtree(recovery)
                    shutil.move(str(backup), str(recovery))
                    recovery_path = str(recovery)
                except OSError:
                    # Even relocating to the documented recovery path failed; the
                    # content is still safe at `backup` itself, so report that path
                    # instead of silently losing it.
                    recovery_path = str(backup)
                return ReplaceResult(
                    False,
                    f"commit failed ({commit_exc}) and automatic restoration also failed "
                    f"({restore_exc}); {target} is MISSING, not preserved; the prior known-good "
                    f"bundle is intentionally left at {recovery_path} for manual recovery",
                    recovery_path,
                )
            return ReplaceResult(
                False,
                f"commit failed ({commit_exc}); automatically restored {target} from the backup copy",
            )
        return ReplaceResult(False, str(commit_exc))
    return ReplaceResult(True)


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

    # Retain known-good: promote a *copy* of the current active bundle into the
    # rollback slot before the canonical active path is mutated, so a failure below
    # always has something correct to restore. The real active bundle is only ever
    # copied from here, never moved or deleted, until the rollback slot promotion is
    # confirmed to have committed (never delete the existing rollback bundle before
    # its replacement is safely staged and promoted).
    moved_prior_active = False
    if had_active:
        incoming_rb = rb.parent / f".{APP_NAME}.rollback-incoming"
        old_rb_backup = rb.parent / f".{APP_NAME}.rollback-old"
        try:
            rb.parent.mkdir(parents=True, exist_ok=True)
            if incoming_rb.exists():
                shutil.rmtree(incoming_rb)
            shutil.copytree(active, incoming_rb)
        except OSError as exc:
            shutil.rmtree(incoming_rb, ignore_errors=True)
            config_after = capture_config_evidence()
            assert_config_unchanged(config_before, config_after)
            return LifecycleResult(
                "install",
                False,
                f"filesystem error staging known-good bundle for retention, active and existing "
                f"rollback bundle left untouched: {exc}",
                asdict(config_before),
                asdict(config_after),
            )

        replace_result = _replace_directory_content(incoming_rb, rb, old_rb_backup)
        # `incoming_rb` is always disposable here: the real active bundle was only
        # ever copied from, never moved, so it remains fully intact regardless of
        # this promotion's outcome.
        shutil.rmtree(incoming_rb, ignore_errors=True)
        if replace_result.preserved_recovery_path is None:
            shutil.rmtree(old_rb_backup, ignore_errors=True)
        if not replace_result.ok:
            config_after = capture_config_evidence()
            assert_config_unchanged(config_before, config_after)
            return LifecycleResult(
                "install",
                False,
                f"filesystem error retaining known-good bundle in the rollback slot: "
                f"{replace_result.reason}; active left untouched",
                asdict(config_before),
                asdict(config_after),
                replace_result.preserved_recovery_path,
            )
        moved_prior_active = True

    try:
        if active.exists():
            shutil.rmtree(active)
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

    cleanup = _clear_pipeline_temp_state()
    config_after = capture_config_evidence()
    assert_config_unchanged(config_before, config_after)
    if not cleanup.ok:
        return LifecycleResult(
            "install",
            False,
            f"install committed and the canonical-path launch probe passed, but pipeline cleanup "
            f"failed afterward: {cleanup.reason}",
            asdict(config_before),
            asdict(config_after),
            str(terminal_recovery_path()) if terminal_recovery_path().exists() else None,
        )
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


def _restore_active_from_backup_after_probe_failure(active: Path, backup: Path) -> ReplaceResult:
    """Restore `active` from `backup` after a post-rollback canonical-path probe
    failure.

    Never moves or risks `backup` itself directly during the ordinary restoration
    attempt: a disposable copy is swapped into `active` instead, via
    `_replace_directory_content`, so a failure during that attempt can never destroy
    `backup`'s own content. `backup` remains the caller's safe fallback until this
    reports success.

    If this restoration attempt itself hits a true double filesystem failure (the
    generic swap helper could neither commit the restoration copy into `active` nor
    move the displaced content back), the content the generic helper relocated to
    `terminal_recovery_path()` is whatever was still stuck at `active` -- the
    lower-value bundle that just failed the post-rollback launch probe -- which is
    exactly the wrong artifact to leave at the pipeline's one documented recovery
    slot. `backup` itself is untouched by any of those moves and is already known
    launchable (it was probe-validated by `validate_bundle_identity(active)` in
    `rollback()` before it was ever copied aside to `backup`), so it is what actually
    belongs at the recovery path. This relocates the true known-good `backup`
    there in place of the failing candidate and discards the failing candidate
    outright, so exactly one recovery bundle exists and it is guaranteed launchable.
    """
    restore_source = active.parent / f".{APP_NAME}.rollback-restore-staging"
    throwaway_backup = active.parent / f".{APP_NAME}.rollback-restore-backup"
    try:
        if restore_source.exists():
            shutil.rmtree(restore_source)
        shutil.copytree(backup, restore_source)
    except OSError as exc:
        shutil.rmtree(restore_source, ignore_errors=True)
        return ReplaceResult(False, f"could not stage a restoration copy from the backup: {exc}")

    result = _replace_directory_content(restore_source, active, throwaway_backup)
    shutil.rmtree(restore_source, ignore_errors=True)

    if result.preserved_recovery_path is None:
        shutil.rmtree(throwaway_backup, ignore_errors=True)
        return result

    recovery = terminal_recovery_path()
    try:
        recovery.parent.mkdir(parents=True, exist_ok=True)
        if recovery.exists():
            shutil.rmtree(recovery)
        shutil.move(str(backup), str(recovery))
    except OSError as exc:
        return ReplaceResult(
            False,
            f"the post-rollback canonical-path probe failed and automatic restoration hit a double "
            f"filesystem failure ({result.reason}); additionally failed to relocate the known-good "
            f"bundle from {backup} to the terminal recovery path ({exc}); it remains safely "
            f"available, untouched, at {backup}",
        )
    return ReplaceResult(
        False,
        f"the post-rollback canonical-path probe failed and automatic restoration hit a double "
        f"filesystem failure (the canonical active path is MISSING, not preserved); the prior "
        f"known-good bundle has been relocated to the terminal recovery path and remains safely "
        f"available, launchable, at {recovery}",
        str(recovery),
    )


def rollback() -> LifecycleResult:
    """Restore the single known-good rollback bundle over the active bundle.

    Validates the existing active bundle's identity, executable, ad-hoc signature,
    and launch probe before any mutation, aborting without mutation if it is foreign
    or malformed -- exactly like `install`. Never deletes the active bundle before a
    working replacement is ready: the rollback bundle is copied into a staging
    location first, and only a working staged copy is swapped in for active (moving
    the existing active bundle to a backup slot rather than deleting it). After the
    swap commits, the restored bundle is launch-probed at the canonical active path
    (never a staging proxy) before rollback is reported successful; a probe failure
    triggers automatic restoration from the backup. Any staging, swap, or
    post-restoration-probe failure leaves the original active bundle exactly as it
    was, EXCEPT in a true double filesystem failure (commit move and the automatic
    restoration move both fail): `active` is then genuinely missing, and the content
    that would otherwise be destroyed is relocated to the bounded terminal recovery
    bundle path (`LifecycleResult.preserved_recovery_path`) instead of being deleted,
    so no recoverable copy of the prior known-good bundle is ever lost.
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
    if active.exists():
        active_validation = validate_bundle_identity(active)
        if not active_validation.ok:
            config_after = capture_config_evidence()
            assert_config_unchanged(config_before, config_after)
            return LifecycleResult(
                "rollback",
                False,
                f"aborted: existing active bundle is foreign or malformed: {active_validation.reason}",
                asdict(config_before),
                asdict(config_after),
            )

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

    replace_result = _replace_directory_content(staged, active, backup)
    shutil.rmtree(staged, ignore_errors=True)

    if not replace_result.ok:
        if replace_result.preserved_recovery_path is None:
            shutil.rmtree(backup, ignore_errors=True)
        config_after = capture_config_evidence()
        assert_config_unchanged(config_before, config_after)
        return LifecycleResult(
            "rollback",
            False,
            f"filesystem error replacing active with staged rollback bundle: {replace_result.reason}",
            asdict(config_before),
            asdict(config_after),
            replace_result.preserved_recovery_path,
        )

    # The swap committed; `backup` still holds the pre-rollback active content,
    # deliberately not yet deleted, in case the canonical-path probe below fails.
    # Only now, at the real canonical active path (never a staging proxy), do we
    # prove the restored bundle actually launches.
    try:
        probe = guarded_launch_probe(active / "Contents" / "MacOS" / EXECUTABLE_NAME)
        probe_failure_note = "" if probe.ok else f"canonical-path launch probe after rollback failed: {probe.reason}"
    except SystemExit:
        probe = None
        probe_failure_note = (
            "canonical-path launch probe after rollback corrupted configuration evidence "
            "(see CONFIG_MUTATED above)"
        )

    if probe is not None and probe.ok:
        shutil.rmtree(backup, ignore_errors=True)
        cleanup = _clear_pipeline_temp_state()
        config_after = capture_config_evidence()
        assert_config_unchanged(config_before, config_after)
        if not cleanup.ok:
            return LifecycleResult(
                "rollback",
                False,
                f"rollback committed and the canonical-path launch probe passed, but pipeline "
                f"cleanup failed afterward: {cleanup.reason}",
                asdict(config_before),
                asdict(config_after),
                str(terminal_recovery_path()) if terminal_recovery_path().exists() else None,
            )
        return LifecycleResult("rollback", True, "", asdict(config_before), asdict(config_after))

    restore_result = _restore_active_from_backup_after_probe_failure(active, backup)
    if restore_result.ok:
        shutil.rmtree(backup, ignore_errors=True)
        cleanup = _clear_pipeline_temp_state()
        config_after = capture_config_evidence()
        if probe is not None:
            assert_config_unchanged(config_before, config_after)
        if not cleanup.ok:
            return LifecycleResult(
                "rollback",
                False,
                f"{probe_failure_note}; automatically restored the prior active bundle, but pipeline "
                f"cleanup failed afterward: {cleanup.reason}",
                asdict(config_before),
                asdict(config_after),
                str(terminal_recovery_path()) if terminal_recovery_path().exists() else None,
            )
        return LifecycleResult(
            "rollback",
            False,
            f"{probe_failure_note}; automatically restored the prior active bundle",
            asdict(config_before),
            asdict(config_after),
        )

    # Restoration failed too.
    config_after = capture_config_evidence()
    if probe is not None:
        assert_config_unchanged(config_before, config_after)
    if restore_result.preserved_recovery_path is not None:
        # The double-failure branch already relocated the true known-good bundle
        # (never the failing candidate) to the terminal recovery path and moved
        # `backup` there in the process, so `backup` no longer exists at its ad hoc
        # path -- the reason text below must not claim otherwise.
        reason = f"{probe_failure_note}; {restore_result.reason}"
    else:
        # `backup` itself was never moved during the restoration attempt (only
        # copied from) and remains fully intact at its ad hoc path.
        reason = (
            f"{probe_failure_note}; automatic restoration also failed ({restore_result.reason}); "
            f"active is NOT confirmed preserved; the prior known-good bundle remains safely available, "
            f"untouched, at {backup}"
        )
    return LifecycleResult(
        "rollback",
        False,
        reason,
        asdict(config_before),
        asdict(config_after),
        restore_result.preserved_recovery_path,
    )


def uninstall() -> LifecycleResult:
    """Remove the active artifact; report remaining documented local state.

    Validates the existing active bundle's identity, executable, ad-hoc signature,
    and launch probe before removing it, aborting without mutation if it is foreign
    or malformed -- exactly like `install` and `rollback`. Runtime configuration is
    never touched.
    """
    config_before = capture_config_evidence()
    active = active_app_path()

    if active.exists():
        active_validation = validate_bundle_identity(active)
        if not active_validation.ok:
            config_after = capture_config_evidence()
            assert_config_unchanged(config_before, config_after)
            return LifecycleResult(
                "uninstall",
                False,
                f"aborted: existing active bundle is foreign or malformed: {active_validation.reason}",
                asdict(config_before),
                asdict(config_after),
            )
        shutil.rmtree(active)
        removed = True
    else:
        removed = False

    cleanup = _clear_pipeline_temp_state()
    config_after = capture_config_evidence()
    assert_config_unchanged(config_before, config_after)

    remaining = {
        "active_removed": removed,
        "rollback_bundle_present": rollback_app_path().exists(),
        "terminal_recovery_bundle_present": terminal_recovery_path().exists(),
        "local_ship_dir_present": local_ship_dir().exists(),
        "support_dir_present": support_dir().exists(),
    }
    if not cleanup.ok:
        return LifecycleResult(
            "uninstall",
            False,
            f"active removal succeeded, but pipeline cleanup failed afterward: {cleanup.reason}; "
            f"remaining state: {json.dumps(remaining)}",
            asdict(config_before),
            asdict(config_after),
            str(terminal_recovery_path()) if terminal_recovery_path().exists() else None,
        )
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
