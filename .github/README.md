# Manual source maintenance and publication

There are exactly two independent release workflows. Neither triggers the other.

* **Bump version**: select a branch and one required mode (`patch`, `minor`, or
  `major`, default `patch`). It creates one source-only direct child of the
  selected immutable event commit, with Actions bot author/committer identities
  and the literal ending trailer
  `Co-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>`.
  It does not build, tag, release, or dispatch another workflow.
* **Build**: select any intended ref with GitHub's built-in ref selector. There
  are no custom inputs. Every job checks out `github.sha`, derives the canonical
  source version, checks publication availability before native/credential
  operations, and builds that immutable source. No default-branch-only restriction
  is introduced. To release after bumping, independently run Build on the updated
  branch. Build can also publish unchanged source if its version is unoccupied.

## Source authority

The later coordinated header in
`1d01e904f9264ec47b227a87dad52c0985830b26` supersedes the older marketing-first
fallback header in `707c1bddc4e782358320018dc28b8a2a6825dd4a`, despite the
historical implementation updating only one key.

The intake authority remains **4.0.6**, with no migration increment. Only six
stale `CURRENT_PROJECT_VERSION` values and the two stale source localization
version tokens are aligned to that existing authority. Source version maintenance
owns exactly:

1. `Activate.xcodeproj/project.pbxproj`: six each of `MARKETING_VERSION` and
   `CURRENT_PROJECT_VERSION`, target/project Development, Deployment, Default;
2. `Info.plist`: required `CFBundleShortVersionString`, optional
   `CFBundleVersion` (absent at intake, not introduced);
3. `English.lproj/InfoPlist.strings`: actual copied display metadata, including
   the embedded version in `CFBundleGetInfoString`.

The helper rejects noncanonical versions, drift, duplicate assignments (including
quoted/inline keys), missing configurations, invalid metadata and unresolved or
cyclic references before writing. Known references remain references. Edits
replace only version token spans, preserving source encoding/BOM, individual line
endings, file modes, unrelated values and optional-key absence. The prebuilt
bundle and its stale UTF-16 localization are not authority and remain unchanged.

## Guarded bump

The executable `.github/hooks/pre-push` is mandatory before edits, on every
guard invocation and again immediately after the final real remote read. Its
raw worktree blob must match its committed `100755` entry; missing/nonexecuting,
symlink and executable replacements fail closed. Keep its executable Git mode
when reviewing/staging the migration.

The selected SHA must equal the exact remote branch. The nonempty commit may
change only the three source paths and must have the selected SHA as its sole
parent. A pre-push hook checks exactly one literal new-SHA/HEAD update and its
actual advertised old SHA/ref, including advance/rewind/delete/same-result races.
Both `push.followTags=false` and `--no-follow-tags` suppress annotated tags.
There is no force, amend, automatic retry or rollback.

## Native scope and package validation

Windows retains the original static CMD invocation of `Activate.sln` with
Release x64, v143 and SDK 10.0. The solution's project name is `activate`;
`Activate.vcxproj` has the existing lower-case Windows OutDir. The exact artifact
is `test/Plugins/activate.bundle/Contents/Windows64/activate.4DX`; no recursive
first-match search or project normalization is performed.

Every Build checkout inherits process-scoped `core.autocrlf=false` using
`GIT_CONFIG_COUNT/KEY_0/VALUE_0`, without changing host configuration. Actual
Windows regular worktree files may differ only in executable mode and only when
their raw bytes match. Selected/index modes remain strict; reparse leaves and
ancestors, nonregular files, raw/staged/reversed changes and hidden flags fail.
Both `git ls-files -v` and `-f` are checked before generated exceptions.

macOS retains `Activate.xcodeproj`, target `Activate`, configuration Default,
`ARCHS="arm64 x86_64"`, `ONLY_ACTIVE_ARCH=NO`, deployment 11.0,
`CODE_SIGNING_ALLOWED=NO`, and the existing explicit
`CONFIGURATION_BUILD_DIR="$PWD/test/Plugins"` override. Native product,
bundle and executable remain lowercase `activate`; display/archives remain
`Activate`. The unchanged embedded legacy phase runs only for Deployment and is
inactive for Default. No frameworks, project signing policy or local-build
behavior is modernized.

Cleanup deletes only exact generated leaves and proven intermediates, after
symlink/reparse prevalidation, with fatal errors. It preserves the tracked
**regular** `Contents/CodeResources`, QuickLook thumbnail, other resources and
siblings; it does not delete entire bundles, `Default`, or lowercase `plugins`.
Final checkout validation preserves immutable HEAD/index and nongenerated raw
bytes, but retains genuinely built tracked outputs instead of resetting them.
Ignored/untracked unexpected sources fail, including under XCBuildData. Only
`build.db`, `build.db-wal`, `build.db-shm` and descendants of 32-lowercase-hex
`.xcbuilddata` directories qualify there.

Unsigned validation precedes signing and does not require the signature.
Final validation requires every packaged leaf to be nonempty, regular and
nonsymlink: executable, plist, English localization, manifest/constants,
Windows binary, both CodeResources leaves and QuickLook thumbnail. It rechecks
XML/binary plist and compiled/text localization versions, exact copied resources,
and downloaded/merged Windows equality. Exact `arm64` and `x86_64` tokens are
mandatory; original extra-slice tolerance is preserved.

Manual Developer ID import, strict deep codesign verification, ZIP/DMG creation,
both notarytool submissions and DMG stapling remain in scope. Notarization
requires both successful exit and strict JSON `Accepted`; duplicate/nonfinite
JSON is rejected. Strict signature and final package checks run after stapling.

## Create-only publication and recovery

Publication requires explicit nonempty `GH_TOKEN`, exact API-canonical
`GITHUB_REPOSITORY=miyako/4d-plugin-activate`, and selected `GITHUB_SHA`.
All release pages, including drafts, are inventoried until an **empty** page;
exact matching API refs and actual `ls-remote` tag absence must also agree.
Auth/network/404, malformed JSON/schema, duplicate/nonfinite data and later-page
errors abort. The constant repository-wide cross-ref publication lock has
`cancel-in-progress: false`; it makes no FIFO guarantee.

After all build/sign/notary/staple operations, availability is checked again.
Only create-only POSTs are used: a tag at selected SHA (verified via API and
actual remote), a new public release with a new positive ID, then exact ZIP/DMG
uploads only to that new ID. Same-SHA races fail too. Body remains empty and
generated notes remain false. Returned asset name, integer size and uploaded
state must match.

**Partial failures are deliberately retained.** A lost response may mean a tag,
release or asset was created even when its ID is unknown. Stop and inspect the
reported tag/release ID/confirmed and uncertain assets manually. Do not blindly
rerun: an occupied version must fail closed. Any recovery or removal of retained
production state requires a separate authorized manual decision. There is no
DELETE, PATCH, update, reuse, clobber, retry or rollback path.

## Offline validation

Requires Python 3, PyYAML, Git, Bash, PowerShell and actionlint. No test skips are
permitted. Fixtures use an isolated artifact directory (`PLUGIN_TEST_SCRATCH`,
or the checkout's Git metadata `offline-tests` directory) and clean up on exit.
No test fixtures are staged or left as untracked source.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
actionlint .github/workflows/*.yml
```

Tests use real local Git/bare repositories and fake `gh`, plus extracted
Bash/PowerShell behind closed PATHs. No native compiler, real signing/notary
tools, production GitHub mutation, real credentials or reference-code execution
is used. These fixtures establish offline command/validation behavior, not
hosted toolchain, Apple service or real Windows runner success.
