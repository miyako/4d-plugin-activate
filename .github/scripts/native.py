"""Exact Activate native outputs, selective cleanup, and unsigned/final gates."""

import argparse
from pathlib import Path, PurePosixPath
import re
import shutil
import stat

from repository import is_link
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
XCODE_DATA = Path("build/XCBuildData")
DIRECTORIES = (Path("build/Activate.build"), BASE / "Activate.build")


def generated(path):
    pure = PurePosixPath(path)
    if "\\" in path or pure.as_posix() != path or pure.is_absolute() or ".." in pure.parts:
        return False
    return (path in set(map(str, (*FILES, WINDOWS, DOWNLOAD)))
            or bool(re.fullmatch(
                r"build/XCBuildData/(?:build\.db(?:-wal|-shm)?|"
                r"[0-9a-f]{32}\.xcbuilddata/.+)", path))
            or any(path.startswith(str(directory) + "/") for directory in DIRECTORIES))


def validate_paths(paths):
    root = Path.cwd().resolve()
    for path in map(Path, paths):
        for parent in (path, *path.parents):
            if parent == Path("."):
                break
            if is_link(parent):
                raise ValueError(f"Refusing symlink/reparse output: {parent}")
        if not path.resolve().is_relative_to(root):
            raise ValueError(f"Output escapes checkout: {path}")
        if path.is_dir():
            for descendant in path.rglob("*"):
                if is_link(descendant):
                    raise ValueError(f"Refusing symlink/reparse output: {descendant}")


def prepare():
    files = (*FILES, WINDOWS)
    validate_paths((*files, *DIRECTORIES, XCODE_DATA))
    for path in files:
        path.unlink(missing_ok=True)
    for path in DIRECTORIES:
        if path.exists():
            shutil.rmtree(path)


def prepare_windows():
    files = tuple(WINDOWS.with_suffix(suffix) for suffix in (".4DX", ".exp", ".lib", ".pdb"))
    directory = Path("Objs/Release")
    validate_paths((*files, directory))
    for path in files:
        path.unlink(missing_ok=True)
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
    validate_paths((*PACKAGE_FILES, DOWNLOAD, *DIRECTORIES, XCODE_DATA))
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
