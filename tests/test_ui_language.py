import json
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
HELPER = ROOT / "bin" / "omarchy-taskwarrior"


class UiLanguageSettingsTest(unittest.TestCase):
    def test_spanish_language_choice_is_persisted_privately(self):
        with tempfile.TemporaryDirectory() as home:
            env = dict(os.environ, HOME=home)
            result = subprocess.run(
                [str(HELPER), "settings-set", "--ui-language", "es"],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            self.assertEqual(json.loads(result.stdout)["uiLanguage"], "es")
            settings = Path(home) / ".local/share/omarchy-taskwarrior/ui-settings.json"
            self.assertEqual(stat.S_IMODE(settings.stat().st_mode), 0o600)
            self.assertEqual(json.loads(settings.read_text())["uiLanguage"], "es")

    def test_legacy_settings_and_projects_are_migrated(self):
        with tempfile.TemporaryDirectory() as home:
            env = dict(os.environ, HOME=home)
            legacy = Path(home) / ".local/share/taskwarrior-time"
            legacy.mkdir(parents=True)
            (legacy / "ui-settings.json").write_text(json.dumps({"uiLanguage": "es"}))
            (legacy / "extra-projects.json").write_text(json.dumps(["personal"]))

            result = subprocess.run(
                [str(HELPER), "settings-get"],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            self.assertEqual(json.loads(result.stdout)["uiLanguage"], "es")
            new_data = Path(home) / ".local/share/omarchy-taskwarrior"
            self.assertEqual(json.loads((new_data / "extra-projects.json").read_text()), ["personal"])
            self.assertEqual(stat.S_IMODE(new_data.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE((new_data / "ui-settings.json").stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE((new_data / "extra-projects.json").stat().st_mode), 0o600)
            self.assertTrue((legacy / "ui-settings.json").exists())

    def test_existing_new_settings_are_not_overwritten_by_legacy_data(self):
        with tempfile.TemporaryDirectory() as home:
            env = dict(os.environ, HOME=home)
            legacy = Path(home) / ".local/share/taskwarrior-time"
            legacy.mkdir(parents=True)
            (legacy / "ui-settings.json").write_text(json.dumps({"uiLanguage": "es"}))
            new_settings = Path(home) / ".local/share/omarchy-taskwarrior/ui-settings.json"
            new_settings.parent.mkdir(parents=True)
            new_settings.write_text(json.dumps({"uiLanguage": "en"}))

            result = subprocess.run(
                [str(HELPER), "settings-get"],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            self.assertEqual(json.loads(result.stdout)["uiLanguage"], "en")

    def test_russian_duration_units_are_rejected(self):
        import runpy

        helper = runpy.run_path(str(HELPER))
        self.assertIsNone(helper["parse_duration_to_seconds"]("1ч"))


if __name__ == "__main__":
    unittest.main()
