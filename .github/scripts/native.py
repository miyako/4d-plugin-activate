"""Exact Activate native outputs, selective cleanup, and unsigned/final gates."""

import argparse
from pathlib import Path, PurePosixPath
import re
import shutil
import stat

import source_version


PRODUCT = "activate"
BASE = Path("test/Plugins")
BUNDLE = BASE / "activate.bundle"
CONTENTS = BUNDLE / "Contents"
FILES = tuple(CONTENTS / relative for relative in (
    "MacOS/activate", "Info.plist", "Resources/English.lproj/InfoPlist.strings",
    "Resources/constants.xlf", "Resources/manifest.json",
    "_CodeSignature/CodeResources",
))
WINDOWS = CONTENTS / "Windows64/activate.4DX"
DOWNLOAD = Path("winbuild/activate.4DX")
PRESERVED = (CONTENTS / "CodeResources", CONTENTS / "QuickLook/Thumbnail.png")
PACKAGE_FILES = (*FILES, WINDOWS, *PRESERVED)
XCODE_DATA = BASE / "XCBuildData"
DIRECTORIES = (BASE / "Activate.build",)
EMPTY_DIRECTORIES = tuple(BASE / path for path in (
    "ExplicitPrecompiledModules", "SwiftExplicitPrecompiledModules", "EagerLinkingTBDs/Default",
))
WINDOWS_FILES = tuple(WINDOWS.with_suffix(suffix) for suffix in (".4DX", ".exp", ".lib", ".pdb"))
WINDOWS_DIRECTORIES = (Path("Objs/Release"),)


def generated(path):
    pure = PurePosixPath(path)
    if "\\" in path or pure.as_posix() != path or pure.is_absolute() or ".." in pure.parts:
        return False
    return (path in set(map(str, (*FILES, WINDOWS, DOWNLOAD)))
            or bool(re.fullmatch(
                r"test/Plugins/XCBuildData/(?:build\.db(?:-wal|-shm)?|"
                r"[0-9a-f]{32}\.xcbuilddata/.+)", path))
            or any(path.startswith(str(directory) + "/") for directory in DIRECTORIES))


def checked_mode(path):
    status = path.lstat()
    if stat.S_ISLNK(status.st_mode) or getattr(status, "st_file_attributes", 0) & 0x400:
        raise ValueError(f"Refusing symlink/reparse output: {path}")
    if not (stat.S_ISDIR(status.st_mode) or stat.S_ISREG(status.st_mode)):
        raise ValueError(f"Refusing nonregular output: {path}")
    return status.st_mode


def no_git_marker(directory):
    if any(entry.name.casefold() == ".git" for entry in directory.iterdir()):
        raise ValueError(f"Refusing nested Git marker in output: {directory}")


def validate_tree(path):
    if path.name.casefold() == ".git":
        raise ValueError(f"Refusing nested Git marker in output: {path}")
    if stat.S_ISDIR(checked_mode(path)):
        for descendant in path.iterdir():
            validate_tree(descendant)


def validate_paths(paths):
    root = Path.cwd().resolve()
    for path in map(Path, paths):
        relative = path.relative_to(root) if path.is_absolute() else path
        if ".." in relative.parts:
            raise ValueError(f"Output escapes checkout: {path}")
        current = Path(".")
        for index, part in enumerate(relative.parts):
            current /= part
            if part.casefold() == ".git":
                raise ValueError(f"Refusing nested Git marker in output: {current}")
            try:
                mode = checked_mode(current)
            except FileNotFoundError:
                break
            if index < len(relative.parts) - 1:
                if not stat.S_ISDIR(mode):
                    raise ValueError(f"Output ancestor must be a regular directory: {current}")
                no_git_marker(current)
            else:
                validate_tree(current)


def validate_targets(files=(), directories=()):
    validate_paths((*files, *directories))
    for paths, predicate, kind in (
        (files, stat.S_ISREG, "regular file"),
        (directories, stat.S_ISDIR, "regular directory"),
    ):
        for path in paths:
            try:
                mode = checked_mode(path)
            except FileNotFoundError:
                continue
            if not predicate(mode):
                raise ValueError(f"Output target must be a {kind}: {path}")


def prepare():
    files = (*FILES, WINDOWS)
    validate_targets(files, (*DIRECTORIES, XCODE_DATA, *EMPTY_DIRECTORIES))
    for path in files:
        path.unlink(missing_ok=True)
    for path in DIRECTORIES:
        if path.exists():
            shutil.rmtree(path)


def prepare_windows():
    validate_targets(WINDOWS_FILES, WINDOWS_DIRECTORIES)
    for path in WINDOWS_FILES:
        path.unlink(missing_ok=True)
    for directory in WINDOWS_DIRECTORIES:
        if directory.exists():
            shutil.rmtree(directory)


def require_file(path):
    validate_paths((path,))
    if path.name not in {entry.name for entry in path.parent.iterdir()}:
        raise ValueError(f"Native leaf spelling differs from exact output: {path}")
    if not stat.S_ISREG(path.lstat().st_mode) or path.stat().st_size == 0:
        raise ValueError(f"Missing, nonregular or empty native output: {path}")


def verify_resources():
    for name in ("manifest.json", "constants.xlf"):
        copied = CONTENTS / "Resources" / name
        require_file(copied)
        if copied.read_bytes() != Path(name).read_bytes():
            raise ValueError(f"Copied resource differs from source: {copied}")


def verify_windows():
    for path in (WINDOWS, DOWNLOAD):
        require_file(path)
    if WINDOWS.read_bytes() != DOWNLOAD.read_bytes():
        raise ValueError("Merged Windows payload differs from downloaded artifact")


def validate_unsigned():
    validate_targets((*PACKAGE_FILES, DOWNLOAD),
                     (BUNDLE, *DIRECTORIES, XCODE_DATA, *EMPTY_DIRECTORIES))
    for path in (*FILES[:-1], *PRESERVED):
        require_file(path)
    source_version.verify_bundle(BUNDLE)
    verify_resources()


def validate_final():
    validate_unsigned()
    for path in PACKAGE_FILES:
        require_file(path)
    verify_windows()


def merge_windows():
    validate_paths((WINDOWS, DOWNLOAD, Path("winbuild")))
    require_file(DOWNLOAD)
    WINDOWS.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(DOWNLOAD, WINDOWS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=(
        "clean-macos", "clean-windows", "validate-unsigned", "validate-final", "merge-windows",
    ))
    phase = parser.parse_args().phase
    {"clean-macos": prepare, "clean-windows": prepare_windows,
     "validate-unsigned": validate_unsigned, "validate-final": validate_final,
     "merge-windows": merge_windows}[phase]()
