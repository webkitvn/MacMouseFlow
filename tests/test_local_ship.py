#!/usr/bin/env python3
"""Unit tests for scripts/local_ship.py (OpenSpec change issue-41-local-ship-pipeline).

All tests operate under an isolated fake $HOME so no real ~/Applications or
~/Library/Application Support state is ever touched.
"""

import pathlib
import plistlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import local_ship  # noqa: E402


def make_bundle(root: pathlib.Path, name="fake.app", bundle_id=None, executable_name=None, exit_code=0):
    bundle_id = bundle_id or local_ship.BUNDLE_ID
    executable_name = executable_name or local_ship.EXECUTABLE_NAME
    bundle = root / name
    macos_dir = bundle / "Contents" / "MacOS"
    macos_dir.mkdir(parents=True)
    c_source = root / f"{name}-main.c"
    c_source.write_text(f"int main(void) {{ return {exit_code}; }}\n")
    subprocess.run(
        ["cc", "-std=c11", str(c_source), "-o", str(macos_dir / executable_name)],
        check=True,
        capture_output=True,
    )
    plist = {
        "CFBundleIdentifier": bundle_id,
        "CFBundleExecutable": executable_name,
        "CFBundlePackageType": "APPL",
    }
    (bundle / "Contents" / "Info.plist").write_bytes(plistlib.dumps(plist))
    subprocess.run(["codesign", "--sign", "-", "--force", str(bundle)], check=True, capture_output=True)
    return bundle


class FakeHomeTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="mmf-local-ship-test-")
        self.tmp_home = pathlib.Path(self._tmp.name)
        self._home_patch = mock.patch.object(local_ship, "home", return_value=self.tmp_home)
        self._home_patch.start()

    def tearDown(self):
        self._home_patch.stop()
        self._tmp.cleanup()


class ConfigEvidenceTests(FakeHomeTestCase):
    def test_creates_opaque_sentinel_when_real_config_absent(self):
        evidence = local_ship.capture_config_evidence()
        self.assertTrue(evidence.is_sentinel)
        self.assertTrue(evidence.exists)
        self.assertEqual(evidence.path, str(local_ship.sentinel_path()))
        self.assertEqual(local_ship.sentinel_path().read_bytes(), local_ship.SENTINEL_MAGIC)

    def test_sentinel_is_stable_and_outside_local_ship_dir(self):
        first = local_ship.capture_config_evidence()
        second = local_ship.capture_config_evidence()
        self.assertEqual(first, second)
        self.assertNotIn("LocalShip", first.path)

    def test_real_config_evidence_used_when_present(self):
        support = local_ship.support_dir()
        support.mkdir(parents=True)
        real = local_ship.config_path()
        real.write_bytes(b"real-config-bytes")
        evidence = local_ship.capture_config_evidence()
        self.assertFalse(evidence.is_sentinel)
        self.assertEqual(evidence.byte_length, len(b"real-config-bytes"))
        self.assertFalse(local_ship.sentinel_path().exists())

    def test_assert_config_unchanged_raises_on_mismatch(self):
        before = local_ship.capture_config_evidence()
        local_ship.sentinel_path().write_bytes(local_ship.SENTINEL_MAGIC + b"tampered")
        after = local_ship.capture_config_evidence()
        with self.assertRaises(SystemExit):
            local_ship.assert_config_unchanged(before, after)

    def test_assert_config_unchanged_passes_when_identical(self):
        before = local_ship.capture_config_evidence()
        after = local_ship.capture_config_evidence()
        local_ship.assert_config_unchanged(before, after)  # no raise


class BundleValidationTests(FakeHomeTestCase):
    def test_accepts_well_formed_ad_hoc_signed_bundle(self):
        bundle = make_bundle(self.tmp_home)
        result = local_ship.validate_bundle_identity(bundle)
        self.assertTrue(result.ok, result.reason)

    def test_rejects_foreign_bundle_id(self):
        bundle = make_bundle(self.tmp_home, bundle_id="com.example.other")
        result = local_ship.validate_bundle_identity(bundle)
        self.assertFalse(result.ok)
        self.assertIn("bundle id", result.reason)

    def test_rejects_unexpected_executable_name(self):
        bundle = make_bundle(self.tmp_home, executable_name="not-macmouseflow")
        result = local_ship.validate_bundle_identity(bundle)
        self.assertFalse(result.ok)
        self.assertIn("executable", result.reason)

    def test_rejects_missing_info_plist(self):
        bundle = self.tmp_home / "malformed.app"
        (bundle / "Contents" / "MacOS").mkdir(parents=True)
        result = local_ship.validate_bundle_identity(bundle)
        self.assertFalse(result.ok)
        self.assertIn("Info.plist", result.reason)

    def test_rejects_failing_launch_probe(self):
        bundle = make_bundle(self.tmp_home, exit_code=7)
        result = local_ship.validate_bundle_identity(bundle)
        self.assertFalse(result.ok)
        self.assertIn("launch probe", result.reason)

    def test_launch_probe_reports_nonzero_exit(self):
        bundle = make_bundle(self.tmp_home, exit_code=3)
        probe = local_ship.launch_probe(bundle / "Contents" / "MacOS" / local_ship.EXECUTABLE_NAME)
        self.assertFalse(probe.ok)
        self.assertIn("3", probe.reason)

    def test_launch_probe_accepts_exit_zero(self):
        bundle = make_bundle(self.tmp_home, exit_code=0)
        probe = local_ship.launch_probe(bundle / "Contents" / "MacOS" / local_ship.EXECUTABLE_NAME)
        self.assertTrue(probe.ok, probe.reason)

    def test_validate_static_identity_does_not_execute_the_candidate(self):
        # A candidate that would fail its launch probe must still pass the static
        # (identity + ad-hoc signature only) check; the launch probe is proven only
        # after the candidate is committed to the canonical active path (install()).
        bundle = make_bundle(self.tmp_home, exit_code=9)
        result = local_ship.validate_static_identity(bundle)
        self.assertTrue(result.ok, result.reason)

    def test_verify_ad_hoc_signature_rejects_non_adhoc_identity(self):
        # No real signing certificate is available in this environment; the rejection
        # branch is exercised by feeding `verify_ad_hoc_signature` a realistic
        # `codesign -dvvv` transcript for a non-ad-hoc (e.g. Developer ID) signature,
        # so the parsing/decision logic itself is tested without needing a paid cert.
        bundle = make_bundle(self.tmp_home)  # genuinely ad-hoc signed; passes --verify
        non_adhoc_transcript = (
            "Executable=" + str(bundle / "Contents" / "MacOS" / local_ship.EXECUTABLE_NAME) + "\n"
            "Identifier=io.github.webkitvn.macmouseflow\n"
            "Format=app bundle with Mach-O thin (arm64)\n"
            "CodeDirectory v=20400 size=1176 flags=0x0(none) hashes=30+3 location=embedded\n"
            "Signature=Apple Development: Example Developer (ABCDE12345)\n"
            "TeamIdentifier=ABCDE12345\n"
        )
        fake_display = subprocess.CompletedProcess(
            args=["codesign", "-dvvv", str(bundle)], returncode=0, stdout="", stderr=non_adhoc_transcript
        )
        with mock.patch.object(local_ship, "_codesign_display", return_value=fake_display):
            result = local_ship.verify_ad_hoc_signature(bundle)
        self.assertFalse(result.ok)
        self.assertIn("not ad-hoc", result.reason)

    def test_verify_ad_hoc_signature_accepts_real_ad_hoc_bundle(self):
        bundle = make_bundle(self.tmp_home)
        result = local_ship.verify_ad_hoc_signature(bundle)
        self.assertTrue(result.ok, result.reason)


class GuardedLaunchProbeTests(FakeHomeTestCase):
    def test_guarded_probe_matches_plain_probe_on_the_happy_path(self):
        bundle = make_bundle(self.tmp_home, exit_code=0)
        executable = bundle / "Contents" / "MacOS" / local_ship.EXECUTABLE_NAME
        self.assertEqual(local_ship.guarded_launch_probe(executable), local_ship.launch_probe(executable))

    def test_guarded_probe_hard_stops_if_config_evidence_changes_during_probe(self):
        bundle = make_bundle(self.tmp_home, exit_code=0)
        executable = bundle / "Contents" / "MacOS" / local_ship.EXECUTABLE_NAME
        real_capture = local_ship.capture_config_evidence
        call_count = {"n": 0}

        def flaky_capture():
            call_count["n"] += 1
            evidence = real_capture()
            if call_count["n"] == 2:
                # Simulate the probe itself having mutated config; must hard-stop
                # before any caller can act on the (otherwise successful) probe result.
                return local_ship.ConfigEvidence(evidence.path, evidence.is_sentinel, True, 999, "tampered")
            return evidence

        with mock.patch.object(local_ship, "capture_config_evidence", side_effect=flaky_capture):
            with self.assertRaises(SystemExit):
                local_ship.guarded_launch_probe(executable)


class LifecycleTests(FakeHomeTestCase):
    def setUp(self):
        super().setUp()
        self.candidate_root = self.tmp_home / "candidates"
        self.candidate_root.mkdir()

    def test_install_from_empty_state_creates_active_and_no_rollback(self):
        candidate = make_bundle(self.candidate_root, name=local_ship.APP_NAME)
        result = local_ship.install(candidate)
        self.assertTrue(result.ok, result.reason)
        self.assertTrue(local_ship.active_app_path().exists())
        self.assertFalse(local_ship.rollback_app_path().exists())

    def test_update_moves_prior_active_to_rollback(self):
        first = make_bundle(self.candidate_root, name="first.app")
        second = make_bundle(self.candidate_root, name="second.app")
        self.assertTrue(local_ship.install(first).ok)
        result = local_ship.install(second)
        self.assertTrue(result.ok, result.reason)
        self.assertTrue(local_ship.rollback_app_path().exists())
        self.assertTrue(local_ship.active_app_path().exists())

    def test_install_retains_exactly_one_rollback_bundle_across_repeated_updates(self):
        for i in range(3):
            candidate = make_bundle(self.candidate_root, name=f"candidate-{i}.app")
            self.assertTrue(local_ship.install(candidate).ok)
        rollback_children = list((local_ship.local_ship_dir() / "rollback").iterdir())
        self.assertEqual(rollback_children, [local_ship.rollback_app_path()])

    def test_install_aborts_without_mutation_when_active_is_foreign(self):
        foreign = make_bundle(self.candidate_root, name="foreign.app", bundle_id="com.example.other")
        local_ship.active_app_path().parent.mkdir(parents=True)
        shutil.copytree(foreign, local_ship.active_app_path())
        before_evidence = local_ship.capture_config_evidence()

        candidate = make_bundle(self.candidate_root, name=local_ship.APP_NAME)
        result = local_ship.install(candidate)

        self.assertFalse(result.ok)
        self.assertFalse(local_ship.rollback_app_path().exists())
        # active bundle must remain the untouched foreign copy
        active_plist = plistlib.loads((local_ship.active_app_path() / "Contents" / "Info.plist").read_bytes())
        self.assertEqual(active_plist["CFBundleIdentifier"], "com.example.other")
        after_evidence = local_ship.capture_config_evidence()
        self.assertEqual(before_evidence, after_evidence)

    def test_install_rejects_malformed_candidate_without_touching_active(self):
        good_active = make_bundle(self.candidate_root, name=local_ship.APP_NAME)
        self.assertTrue(local_ship.install(good_active).ok)

        broken_candidate = self.candidate_root / "broken.app"
        (broken_candidate / "Contents" / "MacOS").mkdir(parents=True)
        result = local_ship.install(broken_candidate)

        self.assertFalse(result.ok)
        self.assertTrue(local_ship.active_app_path().exists())
        self.assertFalse(local_ship.rollback_app_path().exists())

    def test_post_install_canonical_path_probe_failure_triggers_automatic_restoration(self):
        # The failing candidate has a valid identity and a genuine ad-hoc signature, so
        # it passes every pre-mutation check and is genuinely committed to the
        # canonical active path; only then does its launch probe fail there. This is
        # the same commit-then-probe sequence the real pipeline uses, not a synthetic
        # shortcut.
        good = make_bundle(self.candidate_root, name="good.app")
        self.assertTrue(local_ship.install(good).ok)
        good_executable_sha = local_ship.sha256_file(
            local_ship.active_app_path() / "Contents" / "MacOS" / local_ship.EXECUTABLE_NAME
        )
        before_evidence = local_ship.capture_config_evidence()

        failing = make_bundle(self.candidate_root, name="failing.app", exit_code=9)
        result = local_ship.install(failing)

        self.assertFalse(result.ok)
        self.assertIn("canonical-path launch probe failed", result.reason)
        self.assertIn("automatically restored the known-good bundle", result.reason)

        # Automatic restoration: the canonical active path is the known-good bundle
        # again, not the broken candidate, and it still launches.
        active = local_ship.active_app_path()
        self.assertTrue(active.exists())
        active_plist = plistlib.loads((active / "Contents" / "Info.plist").read_bytes())
        self.assertEqual(active_plist["CFBundleIdentifier"], local_ship.BUNDLE_ID)
        restored_sha = local_ship.sha256_file(active / "Contents" / "MacOS" / local_ship.EXECUTABLE_NAME)
        self.assertEqual(restored_sha, good_executable_sha)
        self.assertTrue(local_ship.validate_bundle_identity(active).ok)

        # The single rollback bundle now holds that same known-good content (it was
        # retained there before the failed commit, per "retain known-good, install
        # then probe canonical active path").
        self.assertTrue(local_ship.rollback_app_path().exists())
        rollback_sha = local_ship.sha256_file(
            local_ship.rollback_app_path() / "Contents" / "MacOS" / local_ship.EXECUTABLE_NAME
        )
        self.assertEqual(rollback_sha, good_executable_sha)

        after_evidence = local_ship.capture_config_evidence()
        self.assertEqual(before_evidence, after_evidence)

    def test_first_install_probe_failure_leaves_active_empty_with_nothing_to_restore(self):
        # With no prior active bundle, "restore" has nothing to fall back to; the
        # canonical active path must simply stay empty, not the broken candidate.
        before_evidence = local_ship.capture_config_evidence()
        failing = make_bundle(self.candidate_root, name="failing.app", exit_code=9)
        result = local_ship.install(failing)

        self.assertFalse(result.ok)
        self.assertIn("canonical-path launch probe failed", result.reason)
        self.assertIn("no prior active bundle existed", result.reason)
        self.assertFalse(local_ship.active_app_path().exists())
        self.assertFalse(local_ship.rollback_app_path().exists())
        after_evidence = local_ship.capture_config_evidence()
        self.assertEqual(before_evidence, after_evidence)

    def test_filesystem_error_installing_candidate_is_reported_and_restorable(self):
        good = make_bundle(self.candidate_root, name="good.app")
        self.assertTrue(local_ship.install(good).ok)
        good_executable_sha = local_ship.sha256_file(
            local_ship.active_app_path() / "Contents" / "MacOS" / local_ship.EXECUTABLE_NAME
        )
        before_evidence = local_ship.capture_config_evidence()

        candidate = make_bundle(self.candidate_root, name="candidate.app")
        real_copytree = shutil.copytree

        def flaky_copytree(src, dst, *args, **kwargs):
            # Only the candidate -> canonical-active-path copy fails; the restore
            # copy (rollback -> active) must still succeed for real.
            if pathlib.Path(src) == candidate:
                raise OSError("simulated disk full")
            return real_copytree(src, dst, *args, **kwargs)

        with mock.patch.object(local_ship.shutil, "copytree", side_effect=flaky_copytree):
            result = local_ship.install(candidate)

        self.assertFalse(result.ok)
        self.assertIn("filesystem error installing candidate at canonical active path", result.reason)
        self.assertIn("automatically restored the known-good bundle", result.reason)

        active = local_ship.active_app_path()
        self.assertTrue(active.exists())
        restored_sha = local_ship.sha256_file(active / "Contents" / "MacOS" / local_ship.EXECUTABLE_NAME)
        self.assertEqual(restored_sha, good_executable_sha)

        after_evidence = local_ship.capture_config_evidence()
        self.assertEqual(before_evidence, after_evidence)

    def test_rollback_restores_known_good_bundle(self):
        first = make_bundle(self.candidate_root, name="first.app")
        second = make_bundle(self.candidate_root, name="second.app")
        local_ship.install(first)
        local_ship.install(second)

        result = local_ship.rollback()
        self.assertTrue(result.ok, result.reason)
        self.assertTrue(local_ship.active_app_path().exists())
        self.assertTrue(local_ship.validate_bundle_identity(local_ship.active_app_path()).ok)

    def test_rollback_without_rollback_bundle_fails_cleanly(self):
        result = local_ship.rollback()
        self.assertFalse(result.ok)
        self.assertIn("no rollback bundle", result.reason)

    def test_config_mutation_after_canonical_replacement_restores_known_good(self):
        # Regression: a config-integrity violation surfacing from guarded_launch_probe
        # (a hard SystemExit) *after* the candidate has already been committed to the
        # canonical active path must be caught by install(), which then restores the
        # retained known-good bundle and returns a structured failure - it must never
        # propagate as an uncaught crash that leaves the candidate in place.
        good = make_bundle(self.candidate_root, name="good.app")
        self.assertTrue(local_ship.install(good).ok)
        good_sha = local_ship.sha256_file(
            local_ship.active_app_path() / "Contents" / "MacOS" / local_ship.EXECUTABLE_NAME
        )

        candidate = make_bundle(self.candidate_root, name="candidate.app")
        real_guarded_probe = local_ship.guarded_launch_probe
        calls = {"n": 0}

        def flaky_guarded_probe(executable):
            calls["n"] += 1
            # Call #1 is install()'s pre-mutation validation of the *existing* active
            # bundle (must succeed, or the whole scenario cannot be set up); call #2 is
            # the post-replacement probe of the newly committed candidate at the same
            # canonical path - that is the one this regression targets.
            if calls["n"] == 2:
                local_ship.fail("CONFIG_MUTATED", "simulated integrity violation during canonical-path probe")
            return real_guarded_probe(executable)

        with mock.patch.object(local_ship, "guarded_launch_probe", side_effect=flaky_guarded_probe):
            result = local_ship.install(candidate)

        self.assertFalse(result.ok)
        self.assertIn("corrupted configuration evidence", result.reason)
        self.assertIn("automatically restored the known-good bundle", result.reason)
        active = local_ship.active_app_path()
        self.assertTrue(active.exists())
        restored_sha = local_ship.sha256_file(active / "Contents" / "MacOS" / local_ship.EXECUTABLE_NAME)
        self.assertEqual(restored_sha, good_sha)
        self.assertTrue(local_ship.validate_bundle_identity(active).ok)

    def test_config_mutation_after_first_install_replacement_leaves_active_empty(self):
        # Same violation, but with no prior active bundle: nothing to restore, so the
        # canonical active path must be left empty rather than holding the candidate.
        candidate = make_bundle(self.candidate_root, name=local_ship.APP_NAME)
        real_guarded_probe = local_ship.guarded_launch_probe

        def flaky_guarded_probe(executable):
            # With no prior active bundle, install() calls guarded_launch_probe exactly
            # once: the post-replacement probe of the freshly committed candidate.
            local_ship.fail("CONFIG_MUTATED", "simulated integrity violation during canonical-path probe")
            return real_guarded_probe(executable)

        with mock.patch.object(local_ship, "guarded_launch_probe", side_effect=flaky_guarded_probe):
            result = local_ship.install(candidate)

        self.assertFalse(result.ok)
        self.assertIn("corrupted configuration evidence", result.reason)
        self.assertIn("no prior active bundle existed", result.reason)
        self.assertFalse(local_ship.active_app_path().exists())

    def test_rollback_filesystem_error_while_staging_preserves_active(self):
        first = make_bundle(self.candidate_root, name="first.app")
        second = make_bundle(self.candidate_root, name="second.app")
        self.assertTrue(local_ship.install(first).ok)
        self.assertTrue(local_ship.install(second).ok)  # first.app is now the rollback bundle
        active_sha_before = local_ship.sha256_file(
            local_ship.active_app_path() / "Contents" / "MacOS" / local_ship.EXECUTABLE_NAME
        )
        before_evidence = local_ship.capture_config_evidence()

        rb = local_ship.rollback_app_path()
        real_copytree = shutil.copytree

        def flaky_copytree(src, dst, *args, **kwargs):
            if pathlib.Path(src) == rb:
                raise OSError("simulated disk full while staging rollback")
            return real_copytree(src, dst, *args, **kwargs)

        with mock.patch.object(local_ship.shutil, "copytree", side_effect=flaky_copytree):
            result = local_ship.rollback()

        self.assertFalse(result.ok)
        self.assertIn("filesystem error staging rollback bundle", result.reason)
        active = local_ship.active_app_path()
        self.assertTrue(active.exists())
        active_sha_after = local_ship.sha256_file(active / "Contents" / "MacOS" / local_ship.EXECUTABLE_NAME)
        self.assertEqual(active_sha_after, active_sha_before)
        after_evidence = local_ship.capture_config_evidence()
        self.assertEqual(before_evidence, after_evidence)

    def test_rollback_filesystem_error_while_replacing_preserves_active(self):
        first = make_bundle(self.candidate_root, name="first.app")
        second = make_bundle(self.candidate_root, name="second.app")
        self.assertTrue(local_ship.install(first).ok)
        self.assertTrue(local_ship.install(second).ok)  # first.app is now the rollback bundle
        active_sha_before = local_ship.sha256_file(
            local_ship.active_app_path() / "Contents" / "MacOS" / local_ship.EXECUTABLE_NAME
        )
        before_evidence = local_ship.capture_config_evidence()

        real_move = shutil.move

        def flaky_move(src, dst, *args, **kwargs):
            # Let "move active aside to backup" succeed; fail only the final commit
            # ("move staged rollback copy into active").
            if "rollback-staging" in str(src):
                raise OSError("simulated failure committing rollback")
            return real_move(src, dst, *args, **kwargs)

        with mock.patch.object(local_ship.shutil, "move", side_effect=flaky_move):
            result = local_ship.rollback()

        self.assertFalse(result.ok)
        self.assertIn("filesystem error replacing active with staged rollback bundle", result.reason)
        active = local_ship.active_app_path()
        self.assertTrue(active.exists(), "active must be restored, never left missing")
        active_sha_after = local_ship.sha256_file(active / "Contents" / "MacOS" / local_ship.EXECUTABLE_NAME)
        self.assertEqual(active_sha_after, active_sha_before)
        after_evidence = local_ship.capture_config_evidence()
        self.assertEqual(before_evidence, after_evidence)

    def test_rollback_double_failure_preserves_backup_and_reports_it_honestly(self):
        first = make_bundle(self.candidate_root, name="first.app")
        second = make_bundle(self.candidate_root, name="second.app")
        self.assertTrue(local_ship.install(first).ok)
        self.assertTrue(local_ship.install(second).ok)  # first.app is now the rollback bundle

        active = local_ship.active_app_path()
        backup = active.parent / f".{local_ship.APP_NAME}.rollback-backup"
        before_evidence = local_ship.capture_config_evidence()

        real_move = shutil.move

        def flaky_move(src, dst, *args, **kwargs):
            # Let "move active aside to backup" succeed, but fail BOTH the commit
            # move (staged -> active) and the automatic restoration move
            # (backup -> active), reproducing the double-failure case where the
            # backup is the sole remaining recoverable copy.
            if "rollback-staging" in str(src) or "rollback-backup" in str(src):
                raise OSError("simulated double failure: commit and restoration both fail")
            return real_move(src, dst, *args, **kwargs)

        with mock.patch.object(local_ship.shutil, "move", side_effect=flaky_move):
            result = local_ship.rollback()

        self.assertFalse(result.ok)
        self.assertIn("MISSING, not preserved", result.reason)
        self.assertNotIn("automatically restored", result.reason)
        self.assertEqual(result.preserved_backup_path, str(backup))

        # Active is genuinely gone; the backup must never have been deleted, and
        # must still be a valid, identifiable known-good bundle for manual recovery.
        self.assertFalse(active.exists())
        self.assertTrue(
            backup.exists(), "the last recoverable known-good copy must be preserved, not deleted"
        )
        self.assertTrue(local_ship.validate_bundle_identity(backup).ok)

        after_evidence = local_ship.capture_config_evidence()
        self.assertEqual(before_evidence, after_evidence)

    def test_uninstall_removes_active_and_preserves_rollback_and_config(self):
        candidate = make_bundle(self.candidate_root, name=local_ship.APP_NAME)
        local_ship.install(candidate)
        before_evidence = local_ship.capture_config_evidence()

        result = local_ship.uninstall()
        self.assertTrue(result.ok, result.reason)
        self.assertFalse(local_ship.active_app_path().exists())
        after_evidence = local_ship.capture_config_evidence()
        self.assertEqual(before_evidence, after_evidence)

    def test_uninstall_on_empty_state_is_a_reported_no_op(self):
        result = local_ship.uninstall()
        self.assertTrue(result.ok, result.reason)
        self.assertIn('"active_removed": false', result.reason)


class TransportVerificationTests(FakeHomeTestCase):
    def test_package_and_verify_transport_round_trip(self):
        bundle = make_bundle(self.tmp_home, name=local_ship.APP_NAME)
        zip_path = self.tmp_home / "transport" / "candidate.zip"
        digest = local_ship.package_for_transport(bundle, zip_path)

        extract_dir = self.tmp_home / "received"
        result = local_ship.verify_transport(zip_path, digest, extract_dir)
        self.assertTrue(result.ok, result.reason)

    def test_verify_transport_rejects_tampered_zip(self):
        bundle = make_bundle(self.tmp_home, name=local_ship.APP_NAME)
        zip_path = self.tmp_home / "transport" / "candidate.zip"
        digest = local_ship.package_for_transport(bundle, zip_path)

        zip_path.write_bytes(zip_path.read_bytes() + b"tampered")
        extract_dir = self.tmp_home / "received"
        result = local_ship.verify_transport(zip_path, digest, extract_dir)
        self.assertFalse(result.ok)
        self.assertIn("SHA-256 mismatch", result.reason)


if __name__ == "__main__":
    unittest.main()
