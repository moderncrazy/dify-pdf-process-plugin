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


class PluginReleaseWorkflowTests(unittest.TestCase):
    def workflow(self):
        path = ROOT / ".github/workflows/plugin-release.yml"
        self.assertTrue(path.is_file(), "plugin release workflow must exist")
        return path.read_text(encoding="utf-8")

    def test_workflow_has_release_triggers_and_permission(self):
        workflow = self.workflow()

        self.assertIn('      - "v*"', workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("contents: write", workflow)

    def test_workflow_uses_pinned_official_cli_and_versioned_package(self):
        workflow = self.workflow()

        self.assertIn(
            "dify-plugin-daemon/releases/download/0.0.6/"
            "dify-plugin-linux-amd64",
            workflow,
        )
        self.assertIn('plugin package . -o "$PACKAGE_NAME"', workflow)
        self.assertIn(
            'package_name=${PLUGIN_NAME}-${VERSION}.difypkg', workflow
        )
        self.assertIn('EXPECTED_TAG="v${VERSION}"', workflow)

    def test_workflow_creates_non_overwriting_github_release(self):
        workflow = self.workflow()

        self.assertIn("GH_TOKEN: ${{ github.token }}", workflow)
        self.assertLess(
            workflow.index("gh release view"),
            workflow.index("gh release create"),
        )
        self.assertIn("--verify-tag", workflow)
        self.assertIn("--generate-notes", workflow)

        for marketplace_step in ("PLUGIN_ACTION", "dify-plugins", "gh pr create"):
            with self.subTest(marketplace_step=marketplace_step):
                self.assertNotIn(marketplace_step, workflow)


if __name__ == "__main__":
    unittest.main()
