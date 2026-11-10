"""Narrow cleanup, unsigned/final gates, and actual extracted PowerShell checks."""

import os
from pathlib import Path
import shutil
import stat
import subprocess
from types import SimpleNamespace
from unittest.mock import patch

import yaml

from helper_support import Fixture, GitFixture, ROOT, cwd
import native
import repository


class NativeTests(Fixture):
    def test_selective_cleanup_preserves_regular_signature_pointer_thumbnail_and_siblings(self):
        protected = (*native.PRESERVED, native.CONTENTS / "Resources/custom.txt",
                     "test/Plugins/Default/keep", "test/plugins-other/keep",
                     "build/unrelated/keep", "Objs/Debug/keep")
        for path in protected:
            self.write(path, b"preserved")
        for path in (*native.FILES, native.WINDOWS):
            self.write(path, b"stale")
        for directory in native.DIRECTORIES:
            self.write(directory / "object.o", b"stale")
        with cwd(self.root):
            native.prepare()
            native.prepare()
        for path in protected:
            self.assertEqual((self.root / path).read_bytes(), b"preserved")
        for path in (*native.FILES, native.WINDOWS, *native.DIRECTORIES):
            self.assertFalse((self.root / path).exists(), path)

    def test_windows_cleanup_exact_leaves_release_intermediates_no_broad_bundle_deletion(self):
        protected = (*native.PRESERVED, native.CONTENTS / "Resources/manifest.json",
                     native.CONTENTS / "Windows64/other.dll", "Objs/Debug/keep",
                     "Objs/Release-evil/keep")
        outputs = tuple(native.WINDOWS.with_suffix(s) for s in (".4DX", ".exp", ".lib", ".pdb"))
        for path in protected:
            self.write(path, b"preserved")
        for path in (*outputs, "Objs/Release/main.obj"):
            self.write(path, b"stale")
        with cwd(self.root):
            native.prepare_windows()
            native.prepare_windows()
        for path in protected:
            self.assertEqual((self.root / path).read_bytes(), b"preserved")
        for path in (*outputs, "Objs/Release"):
            self.assertFalse((self.root / path).exists(), path)

    def test_symlink_prevalidation_precedes_first_deletion_for_both_platforms(self):
        cases = ((native.prepare, native.FILES[0], (
            native.FILES[-1], native.DIRECTORIES[-1],
            native.DIRECTORIES[0] / "nested/link", native.XCODE_DATA / "link",
        )), (native.prepare_windows, native.WINDOWS, (
            native.WINDOWS.with_suffix(".pdb"), Path("Objs/Release/nested/link"),
        )))
        for prepare, first, links in cases:
            for where in links:
                with self.subTest(where=where):
                    self.write(first, b"must remain")
                    external = self.write("outside/keep", b"untouched")
                    link = self.root / where
                    link.parent.mkdir(parents=True, exist_ok=True)
                    link.symlink_to(external)
                    with cwd(self.root), self.assertRaisesRegex(ValueError, "symlink"):
                        prepare()
                    self.assertEqual((self.root / first).read_bytes(), b"must remain")
                    self.assertEqual(external.read_bytes(), b"untouched")
                    link.unlink()

    def test_reparse_ancestor_prevalidation_precedes_windows_deletion(self):
        self.write(native.WINDOWS, b"must remain")
        self.write("Objs/Release/object.obj", b"must remain")
        real = Path.lstat

        def reparse(path, *args, **kwargs):
            result = real(path, *args, **kwargs)
            if path == Path("Objs/Release"):
                return SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
            return result

        with cwd(self.root), patch.object(Path, "lstat", reparse):
            with self.assertRaisesRegex(ValueError, "reparse"):
                native.prepare_windows()
        self.assertEqual((self.root / native.WINDOWS).read_bytes(), b"must remain")

    def test_cleanup_io_errors_are_fatal_and_xcode_database_is_not_deleted(self):
        self.write(native.FILES[0], b"stale")
        with cwd(self.root), patch.object(Path, "unlink", side_effect=PermissionError("denied")):
            with self.assertRaises(PermissionError):
                native.prepare()
        self.write(native.DIRECTORIES[0] / "main.o", b"stale")
        with cwd(self.root), patch("shutil.rmtree", side_effect=PermissionError("denied")):
            with self.assertRaises(PermissionError):
                native.prepare()
        database = self.write("test/Plugins/XCBuildData/build.db", b"database bytes")
        with cwd(self.root):
            native.prepare()
        self.assertEqual(database.read_bytes(), b"database bytes")

    def test_unsigned_gate_does_not_require_signature_but_final_does(self):
        self.sources()
        for relative in (*native.FILES[:-1], *native.PRESERVED, native.WINDOWS, native.DOWNLOAD):
            self.write(relative, b"payload")
        self.write(native.CONTENTS / "Info.plist", (self.root / "Info.plist").read_bytes())
        self.write(native.CONTENTS / "Resources" / native.source_version.LOCALIZED,
                   (self.root / native.source_version.LOCALIZED).read_bytes())
        for name in ("manifest.json", "constants.xlf"):
            self.write(name, b"resource")
            self.write(native.CONTENTS / "Resources" / name, b"resource")
        with cwd(self.root):
            native.validate_unsigned()
            with self.assertRaises((ValueError, OSError)):
                native.validate_final()
            self.write(native.FILES[-1], b"signature")
            native.validate_final()
            (self.root / native.DOWNLOAD).write_bytes(b"other-windows")
            with self.assertRaisesRegex(ValueError, "differs"):
                native.validate_final()

    def test_exact_download_does_not_search_nested_or_wrong_case_paths(self):
        self.write("winbuild/nested/activate.4DX", b"wrong")
        self.write("winbuild/Activate.4DX", b"wrong")
        with cwd(self.root), self.assertRaises((ValueError, OSError)):
            native.merge_windows()
        (self.root / "winbuild/Activate.4DX").unlink()
        self.write(native.DOWNLOAD, b"downloaded")
        with cwd(self.root):
            native.merge_windows()
        self.assertEqual((self.root / native.WINDOWS).read_bytes(), b"downloaded")


class CleanupAtomicityTests(Fixture):
    def setUp(self):
        super().setUp()
        self.case_number = 0

    def bad_cleanup_case(self, platform, relative, kind):
        self.case_number += 1
        case = self.root / str(self.case_number)
        case.mkdir()
        if platform == "macos":
            files, directories = (*native.FILES, native.WINDOWS), native.DIRECTORIES
            scopes = (*directories, native.XCODE_DATA, *native.EMPTY_DIRECTORIES)
            prepare = native.prepare
        else:
            files, directories = native.WINDOWS_FILES, native.WINDOWS_DIRECTORIES
            scopes, prepare = directories, native.prepare_windows
        baseline = {}
        for path in (*files, *native.PRESERVED,
                     *(directory / "nested/object.o" for directory in directories)):
            raw = b"must retain before validation: " + str(path).encode()
            target = case / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            baseline[path] = raw
        if platform == "macos":
            database = native.XCODE_DATA / "build.db"
            baseline[database] = b"database retained even on successful cleanup"
            (case / database).parent.mkdir(parents=True, exist_ok=True)
            (case / database).write_bytes(baseline[database])
        for directory in scopes:
            (case / directory).mkdir(parents=True, exist_ok=True)
        target = case / relative
        backup = self.root / ("backup-" + str(self.case_number))
        existing = target.exists()
        if existing:
            target.rename(backup)
        target.parent.mkdir(parents=True, exist_ok=True)
        if kind in ("directory", "reparse-dir"):
            target.mkdir()
        elif kind == "symlink":
            outside = self.write("outside-" + str(self.case_number), b"outside untouched")
            target.symlink_to(outside)
        elif kind == "fifo":
            os.mkfifo(target)
        else:
            target.write_bytes(b"bad output or Git marker")
        real_lstat, real_unlink, real_rmtree = Path.lstat, Path.unlink, shutil.rmtree
        deletions = []

        def lstat(path, *args, **kwargs):
            status = real_lstat(path, *args, **kwargs)
            if path == relative:
                if kind.startswith("reparse"):
                    return SimpleNamespace(st_mode=status.st_mode, st_file_attributes=0x400)
                if kind == "socket":
                    return SimpleNamespace(st_mode=stat.S_IFSOCK)
            return status

        def unlink(path, *args, **kwargs):
            deletions.append(path)
            return real_unlink(path, *args, **kwargs)

        def rmtree(path, *args, **kwargs):
            deletions.append(path)
            return real_rmtree(path, *args, **kwargs)

        with cwd(case), patch.object(Path, "lstat", lstat), \
                patch.object(Path, "unlink", unlink), patch.object(shutil, "rmtree", rmtree):
            with self.assertRaisesRegex(
                ValueError, "target|ancestor|symlink|reparse|nonregular|nested Git",
            ):
                prepare()
        self.assertEqual(deletions, [], "All target validation must precede the FIRST deletion")
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
        else:
            target.unlink()
        if existing:
            backup.rename(target)
        for path, raw in baseline.items():
            self.assertEqual((case / path).read_bytes(), raw, path)
        with cwd(case):
            prepare()
        for path in (*files, *directories):
            self.assertFalse((case / path).exists(), path)
        for path in native.PRESERVED:
            self.assertEqual((case / path).read_bytes(), baseline[path])
        if platform == "macos":
            self.assertEqual((case / native.XCODE_DATA / "build.db").read_bytes(),
                             baseline[native.XCODE_DATA / "build.db"])

    def test_every_macos_cleanup_file_and_directory_type_checked_before_any_deletion(self):
        for path in (*native.FILES, native.WINDOWS):
            for kind in ("directory", "symlink", "fifo", "reparse-file"):
                with self.subTest(path=path, kind=kind):
                    self.bad_cleanup_case("macos", path, kind)
        for path in (*native.DIRECTORIES, native.XCODE_DATA, *native.EMPTY_DIRECTORIES):
            for kind in ("file", "symlink", "fifo", "reparse-dir"):
                with self.subTest(path=path, kind=kind):
                    self.bad_cleanup_case("macos", path, kind)

    def test_every_windows_cleanup_file_and_directory_type_checked_before_any_deletion(self):
        for path in native.WINDOWS_FILES:
            for kind in ("directory", "symlink", "fifo", "reparse-file"):
                with self.subTest(path=path, kind=kind):
                    self.bad_cleanup_case("windows", path, kind)
        for path in native.WINDOWS_DIRECTORIES:
            for kind in ("file", "symlink", "fifo", "reparse-dir"):
                with self.subTest(path=path, kind=kind):
                    self.bad_cleanup_case("windows", path, kind)

    def test_late_ancestors_must_be_regular_directories_without_git_markers(self):
        for platform, ancestor in (
            ("macos", native.WINDOWS.parent), ("windows", Path("Objs")),
        ):
            for kind in ("file", "symlink", "fifo", "reparse-dir"):
                with self.subTest(platform=platform, kind=kind):
                    self.bad_cleanup_case(platform, ancestor, kind)
            for marker in (".git", ".GIT"):
                for kind in ("file", "directory"):
                    with self.subTest(platform=platform, marker=marker, kind=kind):
                        self.bad_cleanup_case(platform, ancestor / marker, kind)

    def test_every_inspected_directory_rejects_nested_git_links_and_nonregular_descendants(self):
        cases = (
            ("macos", (*native.DIRECTORIES, native.XCODE_DATA, *native.EMPTY_DIRECTORIES)),
            ("windows", native.WINDOWS_DIRECTORIES),
        )
        for platform, directories in cases:
            for directory in directories:
                for leaf, kind in (
                    ("nested/.git", "file"), ("nested/.git", "directory"),
                    ("nested/link", "symlink"), ("nested/fifo", "fifo"),
                    ("nested/reparse", "reparse-file"), ("nested/socket", "socket"),
                ):
                    with self.subTest(platform=platform, directory=directory, leaf=leaf, kind=kind):
                        self.bad_cleanup_case(platform, directory / leaf, kind)


class GeneratedTests(GitFixture):
    def test_precise_final_only_generated_classifier_and_retention(self):
        accepted = (
            *native.FILES, native.WINDOWS, native.DOWNLOAD,
            "test/Plugins/XCBuildData/build.db", "test/Plugins/XCBuildData/build.db-wal",
            "test/Plugins/XCBuildData/build.db-shm",
            "test/Plugins/XCBuildData/0123456789abcdef0123456789abcdef.xcbuilddata/build-request.json",
            "test/Plugins/Activate.build/Default/Activate.build/Objects-normal/arm64/main.o",
        )
        for path in accepted:
            target = self.local / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"fresh native bytes")
        with cwd(self.local):
            with self.assertRaises(ValueError):
                repository.verify_checkout(self.sha, generated=native.generated)
            repository.verify_checkout(self.sha, generated=native.generated, final=True)
        for path in accepted:
            self.assertEqual((self.local / path).read_bytes(), b"fresh native bytes")
        for path in (
            "test/Plugins/XCBuildData-evil/build.db", "test/Plugins/XCBuildData/unexpected-source.cpp",
            "test/Plugins/XCBuildData/build.db-evil",
            "test/Plugins/XCBuildData/evil.xcbuilddata/request",
            "build/XCBuildData/build.db", "build/XCBuildData/build.db-wal",
            "build/XCBuildData/build.db-shm",
            "build/XCBuildData/0123456789abcdef0123456789abcdef.xcbuilddata/build-request.json",
            "build/Activate.build/Default/Activate.build/Objects-normal/arm64/main.o",
            "build/Activate.build-evil/main.o", "build/Default/Activate.build/main.o",
            "build/unexpected-source.cpp", "Objs/Release/main.obj",
            "test/Plugins/ExplicitPrecompiledModules/unexpected.pcm",
            "test/Plugins/SwiftExplicitPrecompiledModules/unexpected.swiftmodule",
            "test/Plugins/EagerLinkingTBDs/Default/unexpected.tbd",
            "winbuild/nested/activate.4DX", "test/Plugins/Default/keep",
            "test/plugins/keep", str(native.PRESERVED[0]), str(native.PRESERVED[1]),
            str(native.CONTENTS / "Resources/custom.txt"),
        ):
            with self.subTest(path=path):
                target = self.local / path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"unexpected")
                with cwd(self.local), self.assertRaises(ValueError):
                    repository.verify_checkout(self.sha, generated=native.generated, final=True)
                target.unlink()


class WindowsPowerShellTests(Fixture):
    def setUp(self):
        super().setUp()
        self.pwsh = shutil.which("pwsh")
        self.assertIsNotNone(self.pwsh, "PowerShell is required; no skipped native coverage")
        self.tools = self.root / "closed-path"
        self.tools.mkdir()
        workflow = yaml.load((ROOT / ".github/workflows/release.yml").read_text(),
                             Loader=yaml.BaseLoader)
        step = next(s for s in workflow["jobs"]["build-windows"]["steps"]
                    if s.get("name") == "Validate exact Windows output")
        self.assertEqual(step["shell"], "pwsh")
        self.script = self.write("validate.ps1", step["run"].encode())
        self.target = self.write(native.WINDOWS, b"fresh-windows")

    def run_script(self):
        return subprocess.run(
            [self.pwsh, "-NoLogo", "-NoProfile", "-NonInteractive", "-File", str(self.script)],
            cwd=self.root, env={
                "PATH": str(self.tools), "HOME": str(self.root),
                "POWERSHELL_TELEMETRY_OPTOUT": "1", "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
            }, capture_output=True, text=True, timeout=30,
        )

    def test_extracted_powershell_exact_leaf_positive_and_missing_empty_directory_symlink_negatives(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        outside = self.write("outside.4DX", b"fresh-windows")
        for kind in ("missing", "empty", "directory", "symlink"):
            self.target.unlink()
            if kind == "empty":
                self.target.write_bytes(b"")
            elif kind == "directory":
                self.target.mkdir()
            elif kind == "symlink":
                self.target.symlink_to(outside)
            result = self.run_script()
            self.assertNotEqual(result.returncode, 0, kind)
            if kind == "directory":
                self.target.rmdir()
            elif kind != "missing":
                self.target.unlink()
            self.target.write_bytes(b"fresh-windows")
        directory = self.target.parent
        moved = self.root / "moved"
        directory.rename(moved)
        directory.symlink_to(moved, target_is_directory=True)
        self.assertNotEqual(self.run_script().returncode, 0)
        directory.unlink()
        moved.rename(directory)
        self.assertEqual(self.run_script().returncode, 0)
