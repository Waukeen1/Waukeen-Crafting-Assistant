import tempfile
import unittest
from pathlib import Path
from unittest import mock

import wca_updater


class WcaUpdaterTests(unittest.TestCase):
    def _make_installations(self, root):
        target = root / "target"
        release = root / "release"
        (target / "_internal" / "logs").mkdir(parents=True)
        (release / "_internal").mkdir(parents=True)

        (target / wca_updater.APP_EXE).write_text("old exe", encoding="utf-8")
        (target / "_internal" / "build_info.json").write_text(
            '{"version":"1.0.5"}', encoding="utf-8"
        )
        (target / "_internal" / "settings.ini").write_text(
            "user settings", encoding="utf-8"
        )
        (target / "_internal" / "logs" / "session.txt").write_text(
            "user log", encoding="utf-8"
        )
        (target / "stale.bin").write_text("stale", encoding="utf-8")

        (release / wca_updater.APP_EXE).write_text("new exe", encoding="utf-8")
        (release / "_internal" / "build_info.json").write_text(
            '{"version":"1.0.6"}', encoding="utf-8"
        )
        (release / "_internal" / "settings.ini").write_text(
            "default settings", encoding="utf-8"
        )
        (release / "new.bin").write_text("new", encoding="utf-8")
        return release, target

    def test_in_place_install_preserves_user_data_and_removes_stale_files(self):
        with tempfile.TemporaryDirectory() as root_name:
            release, target = self._make_installations(Path(root_name))

            wca_updater._install_in_place(release, target)

            self.assertEqual(
                (target / wca_updater.APP_EXE).read_text(encoding="utf-8"),
                "new exe",
            )
            self.assertIn(
                "1.0.6",
                (target / "_internal" / "build_info.json").read_text(
                    encoding="utf-8"
                ),
            )
            self.assertEqual(
                (target / "_internal" / "settings.ini").read_text(
                    encoding="utf-8"
                ),
                "user settings",
            )
            self.assertEqual(
                (target / "_internal" / "logs" / "session.txt").read_text(
                    encoding="utf-8"
                ),
                "user log",
            )
            self.assertFalse((target / "stale.bin").exists())
            self.assertTrue((target / "new.bin").is_file())

    def test_in_place_install_restores_backup_after_copy_failure(self):
        with tempfile.TemporaryDirectory() as root_name:
            release, target = self._make_installations(Path(root_name))
            real_copy = wca_updater._copy_release
            call_count = 0

            def flaky_copy(source, destination):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise OSError("copy failed")
                return real_copy(source, destination)

            with mock.patch.object(
                wca_updater, "_copy_release", side_effect=flaky_copy
            ):
                with self.assertRaises(OSError):
                    wca_updater._install_in_place(release, target)

            self.assertEqual(
                (target / wca_updater.APP_EXE).read_text(encoding="utf-8"),
                "old exe",
            )
            self.assertEqual(
                (target / "_internal" / "settings.ini").read_text(
                    encoding="utf-8"
                ),
                "user settings",
            )
            self.assertTrue((target / "stale.bin").is_file())

    def test_in_place_install_keeps_backup_if_rollback_also_fails(self):
        with tempfile.TemporaryDirectory() as root_name:
            root = Path(root_name)
            release, target = self._make_installations(root)
            backup_parent = root / "retained-backup"

            with (
                mock.patch.object(
                    wca_updater.tempfile,
                    "mkdtemp",
                    return_value=str(backup_parent),
                ),
                mock.patch.object(
                    wca_updater,
                    "_copy_release",
                    side_effect=OSError("copy failed"),
                ),
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "Yedek klasoru"
                ):
                    wca_updater._install_in_place(release, target)

            backup = backup_parent / "installation"
            self.assertTrue((backup / wca_updater.APP_EXE).is_file())
            self.assertEqual(
                (backup / "_internal" / "settings.ini").read_text(
                    encoding="utf-8"
                ),
                "user settings",
            )


if __name__ == "__main__":
    unittest.main()
