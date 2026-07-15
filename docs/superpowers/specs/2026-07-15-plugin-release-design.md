# PDF Process Plugin Release Design

## Goal

Publish version `1.0.1` of the PDF Process plugin as a GitHub Release in
`moderncrazy/dify-pdf-process-plugin`, with an installable
`pdf_process-1.0.1.difypkg` attachment and a reusable tag-driven packaging
workflow.

## Release Identity

- Change the top-level plugin version in `manifest.yaml` from `1.0.0` to
  `1.0.1`.
- Keep `meta.version` at `0.0.1`; it is the manifest schema version, not the
  plugin release version.
- Change the plugin author from `kalochin` to `moderncrazy` in the manifest,
  provider identity, and every tool identity.
- Update the README author and repository links to `moderncrazy`.
- Use Git tag `v1.0.1`, Release title `PDF Process v1.0.1`, and package filename
  `pdf_process-1.0.1.difypkg`.

## Packaging Workflow

Add `.github/workflows/plugin-release.yml`, based on the packaging pattern in
`moderncrazy/dify-plugin-database` but targeting a GitHub Release instead of a
Marketplace pull request.

The workflow will:

1. Run on pushed tags matching `v*` and support manual dispatch with an
   existing tag as input.
1. Check out the tagged source.
1. Read the top-level `name` and `version` fields from `manifest.yaml`.
1. Reject the run if the release tag is not exactly `v<manifest-version>`.
1. Download the pinned official Dify plugin CLI used by the reference
   repository (`0.0.6`, Linux AMD64).
1. Package the repository with `dify-plugin plugin package` into
   `<name>-<version>.difypkg`.
1. Fail if the GitHub Release already exists, otherwise create it with generated
   notes.
1. Upload the `.difypkg` using the repository-provided `GITHUB_TOKEN` with
   `contents: write` permission.

The workflow will not require `PLUGIN_ACTION`, open a Marketplace pull request,
or commit generated binary packages to the source branch.

## Local Validation and Publication

Before publication:

- verify all author fields and version fields;
- run the existing unit tests, Ruff checks, Markdown formatting checks, and
  Python compilation checks;
- download the same pinned Dify CLI and produce a local package outside the Git
  index;
- verify the package exists, is non-empty, is named correctly, and contains the
  updated manifest and runtime files; and
- verify the worktree contains no generated package before committing.

Publication order:

1. Commit the identity, version, README, tests, and workflow changes.
1. Push `main` to `origin`.
1. Create annotated tag `v1.0.1` at the verified release commit.
1. Push only that tag.
1. Wait for the GitHub Actions workflow and verify the public Release points to
   the tagged commit and contains `pdf_process-1.0.1.difypkg`.

No force push, tag replacement, or Release overwrite is allowed. If tag
`v1.0.1` or the Release already exists, publication stops for review.

## Testing

Add focused tests that verify:

- the top-level plugin version is `1.0.1` while `meta.version` remains
  `0.0.1`;
- every manifest, provider, and tool identity author is `moderncrazy`;
- README links point to the new owner and repository;
- the workflow triggers on version tags and manual dispatch;
- the workflow validates tag-to-manifest version equality;
- the package filename is derived as `pdf_process-1.0.1.difypkg`; and
- Release creation uses `GITHUB_TOKEN` and `contents: write` without the
  reference repository's `PLUGIN_ACTION` or Marketplace PR steps.

## Failure Handling

- A version/tag mismatch fails before packaging.
- A CLI download or package failure prevents Release creation.
- A missing package prevents upload.
- A pre-existing tag or Release stops local publication rather than mutating
  published history.
- A failed GitHub Actions run leaves the source commit and tag intact for
  diagnosis; fixes require a new commit and version decision rather than a
  forced tag move.
