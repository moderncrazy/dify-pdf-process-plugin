import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PluginReleaseIdentityTests(unittest.TestCase):
    def test_manifest_release_and_schema_versions(self):
        manifest = (ROOT / "manifest.yaml").read_text(encoding="utf-8")

        self.assertRegex(manifest, r"(?m)^version: 1\.0\.1$")
        self.assertRegex(manifest, r"(?m)^  version: 0\.0\.1$")

    def test_all_plugin_identity_authors_are_moderncrazy(self):
        identity_files = [
            ROOT / "manifest.yaml",
            ROOT / "provider/pdf_process.yaml",
            *sorted((ROOT / "tools").glob("*.yaml")),
        ]

        for path in identity_files:
            with self.subTest(path=path.relative_to(ROOT)):
                content = path.read_text(encoding="utf-8")
                self.assertRegex(content, r"(?m)^\s*author: moderncrazy$")
                self.assertNotIn("kalochin", content.lower())

    def test_readme_uses_moderncrazy_repository_identity(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("moderncrazy/dify-pdf-process-plugin", readme)
        self.assertNotIn("fdb02983rhy", readme)
        self.assertNotIn("Kalo Chin", readme)


if __name__ == "__main__":
    unittest.main()
