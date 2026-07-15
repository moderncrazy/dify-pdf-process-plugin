# PDF Process Plugin v1.0.1 Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Publish an installable `pdf_process-1.0.1.difypkg` on GitHub Release `v1.0.1`, with all plugin author metadata owned by `moderncrazy` and a reusable tag-driven packaging workflow.

**Architecture:** Keep the plugin runtime unchanged. Add repository-level contract tests for release metadata and workflow behavior, update the existing YAML/README identities, and add one GitHub Actions workflow that checks out an immutable tag, validates it against `manifest.yaml`, packages with pinned Dify CLI `0.0.6`, and creates a non-overwriting GitHub Release.

**Tech Stack:** Python `unittest`, YAML manifests, GitHub Actions, POSIX shell, GitHub CLI, official Dify plugin CLI `0.0.6`.

## Global Constraints

- Do not change PDF runtime behavior or add production dependencies.
- Keep `manifest.yaml` `meta.version` at `0.0.1`; only the top-level plugin version becomes `1.0.1`.
- Do not commit `.difypkg` files or credentials.
- Do not overwrite an existing tag or Release.
- Package locally outside the repository before publication.
- Use small commits after each verified task.

______________________________________________________________________

### Task 1: Lock the release identity with tests

**Files:**

- Create: `tests/test_plugin_release.py`
- Modify: `manifest.yaml`
- Modify: `provider/pdf_process.yaml`
- Modify: `tools/pdf_multi_pages_extractor.yaml`
- Modify: `tools/pdf_page_counter.yaml`
- Modify: `tools/pdf_single_page_extractor.yaml`
- Modify: `tools/pdf_splitter.yaml`
- Modify: `tools/pdf_to_png.yaml`
- Modify: `README.md`

**Step 1: Write the failing identity tests**

Create `tests/test_plugin_release.py` using `unittest`. Read repository files as UTF-8 text and assert:

```python
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
```

**Step 2: Run the new test and confirm RED**

Run:

```bash
.venv/bin/python -m unittest tests.test_plugin_release -v
```

Expected: failures for the old `1.0.0` version, `kalochin` authors, and old README identity.

**Step 3: Make the minimal metadata changes**

- Set only the top-level `manifest.yaml` `version` to `1.0.1`.
- Set `author: moderncrazy` in the manifest, provider, and all five tool YAML files.
- Update the README author text and GitHub repository URLs to `moderncrazy/dify-pdf-process-plugin`.
- Leave runtime source, dependencies, and schema version untouched.

**Step 4: Run the identity tests and confirm GREEN**

Run:

```bash
.venv/bin/python -m unittest tests.test_plugin_release -v
```

Expected: all identity tests pass.

**Step 5: Commit the identity task**

```bash
git add manifest.yaml provider/pdf_process.yaml tools/*.yaml README.md tests/test_plugin_release.py
git commit -m "chore: prepare plugin v1.0.1"
```

______________________________________________________________________

### Task 2: Add and test the tag-driven Release workflow

**Files:**

- Modify: `tests/test_plugin_release.py`
- Create: `.github/workflows/plugin-release.yml`

**Step 1: Add failing workflow contract tests**

Extend `tests/test_plugin_release.py` with a second test class. Assert that the workflow:

- exists;
- listens for `v*` tags and `workflow_dispatch`;
- grants `contents: write`;
- downloads the official Linux AMD64 CLI from Dify plugin daemon release `0.0.6`;
- executes `plugin package . -o`;
- derives `${PLUGIN_NAME}-${VERSION}.difypkg`;
- compares the selected tag with `v${VERSION}`;
- exports `GH_TOKEN: ${{ github.token }}`;
- checks `gh release view` before calling `gh release create` with `--verify-tag` and `--generate-notes`; and
- does not contain `PLUGIN_ACTION`, `dify-plugins`, or `gh pr create`.

Use plain text assertions so tests add no YAML dependency.

**Step 2: Run the workflow tests and confirm RED**

Run:

```bash
.venv/bin/python -m unittest tests.test_plugin_release -v
```

Expected: workflow tests fail because `.github/workflows/plugin-release.yml` does not exist.

**Step 3: Implement the workflow**

Create `.github/workflows/plugin-release.yml` with these stages:

1. Resolve the tag from `github.ref_name` for tag pushes or the required `tag` input for manual dispatch.
2. Check out exactly the resolved tag using `actions/checkout@v4`.
3. Read the first-column `name:` and `version:` values from `manifest.yaml`, require `RELEASE_TAG=v${VERSION}`, and expose `plugin_name`, `version`, and `package_name=${PLUGIN_NAME}-${VERSION}.difypkg` as step outputs.
4. Download `https://github.com/langgenius/dify-plugin-daemon/releases/download/0.0.6/dify-plugin-linux-amd64` with `curl -fL --retry 3`, then make it executable.
5. Run `dify-plugin plugin package . -o "$PACKAGE_NAME"` and `test -s "$PACKAGE_NAME"`.
6. With `GH_TOKEN: ${{ github.token }}`, fail explicitly if `gh release view "$RELEASE_TAG"` succeeds.
7. Create the Release with the package attachment, `--verify-tag`, `--generate-notes`, and title `PDF Process $RELEASE_TAG`.

Set repository permission only to:

```yaml
permissions:
  contents: write
```

Quote the glob in the tag trigger so YAML does not parse `*` as an alias.

**Step 4: Run workflow contract and syntax checks**

Run:

```bash
.venv/bin/python -m unittest tests.test_plugin_release -v
ruby -e 'require "yaml"; YAML.load_file(".github/workflows/plugin-release.yml", aliases: true); puts "workflow yaml ok"'
```

Expected: tests pass and Ruby prints `workflow yaml ok`.

**Step 5: Commit the workflow task**

```bash
git add .github/workflows/plugin-release.yml tests/test_plugin_release.py
git commit -m "ci: release packaged plugin from tags"
```

______________________________________________________________________

### Task 3: Verify the repository and build the exact local artifact

**Files:**

- Verify only; do not add generated files.

**Step 1: Run the full repository verification suite**

Run:

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/ruff check .
.venv/bin/python -m mdformat --check README.md docs
.venv/bin/python -m compileall -q main.py provider tools tests
```

Expected: every command exits successfully.

**Step 2: Download the matching local Dify CLI**

On the current Apple Silicon host, download the `0.0.6` Darwin ARM64 asset outside the repository:

```bash
curl -fL --retry 3 -o /tmp/dify-plugin-0.0.6-darwin-arm64 https://github.com/langgenius/dify-plugin-daemon/releases/download/0.0.6/dify-plugin-darwin-arm64
chmod +x /tmp/dify-plugin-0.0.6-darwin-arm64
```

If that official release has no matching host asset, stop and report the packaging blocker instead of switching CLI versions silently.

**Step 3: Package outside the Git index**

Run:

```bash
/tmp/dify-plugin-0.0.6-darwin-arm64 plugin package . -o /tmp/pdf_process-1.0.1.difypkg
test -s /tmp/pdf_process-1.0.1.difypkg
file /tmp/pdf_process-1.0.1.difypkg
unzip -l /tmp/pdf_process-1.0.1.difypkg
unzip -p /tmp/pdf_process-1.0.1.difypkg manifest.yaml
shasum -a 256 /tmp/pdf_process-1.0.1.difypkg
```

Expected: the artifact is non-empty, contains `manifest.yaml`, Python runtime files, providers, and tools, and its embedded manifest reports `version: 1.0.1` and `author: moderncrazy`.

**Step 4: Confirm the generated package is untracked and review changes**

Run:

```bash
git status --short
git diff --check
git log --oneline origin/main..HEAD
```

Expected: no `.difypkg` under the repository, no whitespace errors, and only the planned commits are ahead of `origin/main`.

______________________________________________________________________

### Task 4: Publish main and the immutable release tag

**Files:**

- No source changes.

**Step 1: Integrate the verified implementation into local main**

From the primary worktree, fast-forward `main` to the verified implementation branch. Do not use a force update. Re-run:

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/ruff check .
git status --short --branch
```

Expected: tests and lint pass and `main` is clean.

**Step 2: Push main and verify the remote commit**

Run:

```bash
git push origin main
git rev-parse HEAD
git ls-remote origin refs/heads/main
```

Expected: local and remote main commit IDs match.

**Step 3: Prove the tag and Release do not exist**

Run:

```bash
git ls-remote --tags origin refs/tags/v1.0.1
curl -sS -o /dev/null -w '%{http_code}\n' https://api.github.com/repos/moderncrazy/dify-pdf-process-plugin/releases/tags/v1.0.1
```

Expected: no remote tag output and HTTP `404`. Stop if either already exists.

**Step 4: Create and push the annotated tag**

Run:

```bash
git tag -a v1.0.1 -m "PDF Process v1.0.1"
git push origin refs/tags/v1.0.1
```

Expected: the tag is accepted without force and starts the Release workflow.

**Step 5: Monitor and verify the GitHub Release**

Poll the GitHub Actions and Releases APIs without changing repository state. Verify:

- the tag-triggered `Package and Release Plugin` workflow completed successfully;
- Release `v1.0.1` exists at `https://github.com/moderncrazy/dify-pdf-process-plugin/releases/tag/v1.0.1`;
- its target resolves to the verified release commit; and
- it contains one non-empty asset named `pdf_process-1.0.1.difypkg`.

Download the published asset to a temporary path and compare its SHA-256 with the locally produced artifact when the deterministic CLI output permits an exact match. If hashes differ, inspect both archives and verify their file lists and embedded manifest before reporting the difference.

**Step 6: Final clean-state check**

Run:

```bash
git status --short --branch
git show --stat --oneline v1.0.1
git ls-remote origin refs/heads/main refs/tags/v1.0.1
```

Expected: clean `main`, published tag, matching remote main, and no generated package committed.
