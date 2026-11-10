"""Extracted workflow shells run only behind closed-PATH native/credential doubles."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET

import yaml

from helper_support import Fixture, ROOT, original, source
import native


WORKFLOW = ROOT / ".github/workflows/release.yml"
STUB = r'''#!PYTHON
import base64, json, os, pathlib, plistlib, shutil, sys
tool, args = pathlib.Path(sys.argv[0]).name, sys.argv[1:]
with open(os.environ["NATIVE_LOG"], "a") as out:
    out.write(json.dumps([tool, *args]) + "\n")
if os.environ.get("FAIL_TOOL") == tool:
    sys.exit(23)
contents = pathlib.Path("test/Plugins/activate.bundle/Contents")
if tool == "python3":
    if args and args[0].endswith("release.py"):
        assert os.environ["GH_TOKEN"] == "offline-only"
        assert os.environ["GITHUB_REPOSITORY"] == "miyako/4d-plugin-activate"
        assert args[2:4] == ["--sha", os.environ["GITHUB_SHA"]]
        if args[1] == "publish":
            assert args[4:] == [f"Activate-{os.environ['VERSION']}.zip",
                                f"Activate-{os.environ['VERSION']}.dmg"]
        if os.environ.get("FAIL_PUBLICATION") or (
                args[1] == "preflight" and os.environ.get("FAIL_PREFLIGHT")):
            sys.exit(9)
    else:
        os.execv(sys.executable, [sys.executable, *args])
elif tool == "xcodebuild":
    assert args == ["-project", "Activate.xcodeproj", "-target", "Activate",
                    "-configuration", "Default", "ARCHS=arm64 x86_64", "ONLY_ACTIVE_ARCH=NO",
                    "MACOSX_DEPLOYMENT_TARGET=11.0", "CODE_SIGNING_ALLOWED=NO",
                    "CONFIGURATION_BUILD_DIR=" + os.getcwd() + "/test/Plugins", "build"]
    for relative in ("MacOS/activate", "Info.plist", "Resources/manifest.json",
                     "Resources/constants.xlf", "Resources/English.lproj/InfoPlist.strings",
                     "_CodeSignature/CodeResources", "Windows64/activate.4DX"):
        assert not (contents / relative).exists(), relative
    if not os.environ.get("STALE_BUILD"):
        (contents / "MacOS").mkdir(parents=True, exist_ok=True)
        (contents / "MacOS/activate").write_bytes(b"fresh-macos")
        (contents / "Info.plist").write_bytes(plistlib.dumps(
            plistlib.loads(pathlib.Path("Info.plist").read_bytes()), fmt=plistlib.FMT_BINARY))
        (contents / "Resources/English.lproj").mkdir(parents=True, exist_ok=True)
        (contents / "Resources/English.lproj/InfoPlist.strings").write_bytes(
            pathlib.Path("English.lproj/InfoPlist.strings").read_bytes().decode().encode("utf-16"))
        for resource in ("manifest.json", "constants.xlf"):
            shutil.copyfile(resource, contents / "Resources" / resource)
        db = pathlib.Path("test/Plugins/XCBuildData")
        db.mkdir(parents=True, exist_ok=True)
        for name in ("build.db", "build.db-wal", "build.db-shm"):
            (db / name).write_bytes(b"fresh-database")
        product = pathlib.Path("test/Plugins/Activate.build/Default/Activate.build/Objects-normal/arm64")
        product.mkdir(parents=True, exist_ok=True)
        (product / "4DPlugin-activate.o").write_bytes(b"fresh-object")
        for empty in ("ExplicitPrecompiledModules", "SwiftExplicitPrecompiledModules",
                      "EagerLinkingTBDs/Default"):
            pathlib.Path("test/Plugins", empty).mkdir(parents=True, exist_ok=True)
elif tool == "lipo":
    assert args == ["-archs", str(contents / "MacOS/activate")]
    print(os.environ.get("ARCHES", "arm64 x86_64"))
elif tool == "base64":
    pathlib.Path(args[args.index("-o")+1]).write_bytes(base64.b64decode(sys.stdin.read()))
elif tool == "security":
    if args[0] == "find-identity":
        print("" if os.environ.get("MISSING_IDENTITY") else
              '  1) OFFLINE "Developer ID Application: Fixture"')
elif tool == "codesign":
    if "--verify" in args and os.environ.get("FAIL_VERIFY"):
        sys.exit(7)
    if "--verify" not in args:
        (contents / "_CodeSignature").mkdir(exist_ok=True)
        (contents / "_CodeSignature/CodeResources").write_bytes(b"fresh-signature")
elif tool in ("ditto", "hdiutil"):
    suffix = "zip" if tool == "ditto" else "dmg"
    assert args[-1] == f"Activate-{os.environ['VERSION']}.{suffix}"
    pathlib.Path(args[-1]).write_bytes(b"offline-package")
elif tool == "xcrun":
    if args[:2] == ["notarytool", "submit"]:
        print(os.environ.get("NOTARY_JSON", json.dumps({
            "status": os.environ.get("NOTARY_STATUS", "Accepted")})))
        sys.exit(int(os.environ.get("NOTARY_EXIT", "0")))
    elif args[:2] == ["stapler", "staple"]:
        sys.exit(int(os.environ.get("STAPLE_EXIT", "0")))
    else:
        assert args[:2] == ["notarytool", "store-credentials"], args
else:
    sys.exit("UNSTUBBED TOOL: " + tool)
'''


class NativeWorkflowTests(Fixture):
    def setUp(self):
        super().setUp()
        self.checkout = self.root / "checkout"
        self.checkout.mkdir()
        self.bin = self.root / "closed-path"
        self.bin.mkdir()
        self.log = self.root / "native.jsonl"
        for tool in ("python3", "xcodebuild", "lipo", "base64", "security",
                     "codesign", "ditto", "hdiutil", "xcrun"):
            path = self.bin / tool
            path.write_text(STUB.replace("PYTHON", sys.executable))
            path.chmod(0o755)
        for tool in ("bash", "grep", "head", "sed"):
            (self.bin / tool).symlink_to(shutil.which(tool))
        version = source.read(ROOT)
        self.env = {
            "PATH": str(self.bin), "HOME": str(self.checkout), "LC_ALL": "C",
            "RUNNER_TEMP": str(self.checkout), "NATIVE_LOG": str(self.log),
            "SOURCE_VERSION": version, "PRODUCT_NAME": "Activate", "BASE_DIR": "test",
            "MACOS_DEPLOYMENT_TARGET": "11.0", "VERSION": version,
            "KEYCHAIN_PATH": str(self.checkout / "offline.keychain"),
            "BUNDLE_PATH": str(native.BUNDLE), "GITHUB_ENV": str(self.checkout / "github-env"),
            "GITHUB_SHA": "a" * 40, "GH_TOKEN": "offline-only",
            "GITHUB_REPOSITORY": "miyako/4d-plugin-activate",
            "PYTHONDONTWRITEBYTECODE": "1",
            "CERT_BASE64": "b2ZmbGluZQ==", "CERT_PASSWORD": "offline-only",
            "KEYCHAIN_PASSWORD": "offline-only", "APPLE_ID": "offline@example.invalid",
            "TEAM_ID": "OFFLINEONLY", "APP_PASSWORD": "offline-only",
        }
        shutil.copytree(ROOT / ".github/scripts", self.checkout / ".github/scripts",
                        ignore=shutil.ignore_patterns("__pycache__"))
        self.sources(self.checkout)
        for relative in ("manifest.json", "constants.xlf"):
            (self.checkout / relative).write_bytes(original(relative))
        self.jobs = yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader)["jobs"]
        self.contents = self.checkout / native.CONTENTS
        self.protected = {}
        for relative in (*native.PRESERVED, native.CONTENTS / "Resources/custom.txt",
                         Path("test/Plugins/Default/keep"),
                         Path("test/plugins-other/keep"), Path("build/unrelated/keep")):
            path = self.checkout / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"preserved")
            self.protected[path] = b"preserved"
        for relative in (*native.FILES, native.WINDOWS):
            path = self.checkout / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"stale")
        download = self.checkout / native.DOWNLOAD
        download.parent.mkdir()
        download.write_bytes(b"downloaded-windows")

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def step(self, job, name, success=True):
        step = next(step for step in self.jobs[job]["steps"] if step.get("name") == name)
        self.assertNotIn("${{", step["run"])
        self.assertEqual(step.get("shell", "bash"), "bash")
        result = subprocess.run(
            ["/bin/bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", step["run"]],
            cwd=self.checkout, env=self.env, capture_output=True, text=True, timeout=30,
        )
        if success is not None:
            self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return result

    def mac_step(self, name, success=True):
        return self.step("build-macos", name, success)

    def build(self):
        self.mac_step("build macOS plugin (universal)")

    def pipeline(self):
        for job in ("version", "build-macos"):
            for step in self.jobs[job]["steps"]:
                if "run" in step:
                    result = self.step(job, step["name"], None)
                    if result.returncode:
                        return result
        return result

    def test_complete_real_shell_pipeline_and_order_retains_preserved_regular_leaves(self):
        result = self.pipeline()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.contents / "MacOS/activate").read_bytes(), b"fresh-macos")
        self.assertEqual((self.checkout / native.WINDOWS).read_bytes(), b"downloaded-windows")
        self.assertEqual((self.contents / "_CodeSignature/CodeResources").read_bytes(), b"fresh-signature")
        for path, raw in self.protected.items():
            self.assertEqual(path.read_bytes(), raw)
        calls = self.calls()
        index = lambda test: next(i for i, call in enumerate(calls) if test(call))
        ordered = [
            index(lambda call: "preflight" in call),
            index(lambda call: call[0] == "xcodebuild"),
            index(lambda call: call[0] == "codesign"),
            index(lambda call: call[0] == "ditto"),
            index(lambda call: call[:3] == ["xcrun", "stapler", "staple"]),
            index(lambda call: "publish" in call),
        ]
        self.assertEqual(ordered, sorted(ordered))
        self.assertEqual(sum(call[:3] == ["xcrun", "notarytool", "submit"] for call in calls), 2)
        self.assertTrue(all("--strict" in call and "--deep" in call for call in calls
                            if call[0] == "codesign" and "--verify" in call))

    def test_pipeline_source_version_is_dynamic(self):
        before, version = self.env["VERSION"], "3.2.1"
        for path in source.SOURCE_PATHS:
            target = self.checkout / path
            target.write_bytes(target.read_bytes().replace(before.encode(), version.encode()))
        self.env.update(SOURCE_VERSION=version, VERSION=version)
        self.assertEqual(source.read(self.checkout), version)
        result = self.pipeline()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.checkout / f"Activate-{version}.zip").is_file())

    def test_cleanup_error_precedes_xcode(self):
        path = self.contents / "Info.plist"
        path.unlink()
        path.mkdir()
        self.mac_step("build macOS plugin (universal)", False)
        self.assertFalse(any(call[0] == "xcodebuild" for call in self.calls()))

    def test_exact_universal_tokens_allow_original_extra_architectures(self):
        self.env["STALE_BUILD"] = "1"
        self.build()
        self.mac_step("verify universal binary", False)
        self.env.pop("STALE_BUILD")
        self.build()
        binary = self.contents / "MacOS/activate"
        binary.write_bytes(b"")
        self.mac_step("verify universal binary", False)
        binary.write_bytes(b"fresh")
        for arches in ("arm64e x86_64", "arm64 x86_64h", ""):
            self.env["ARCHES"] = arches
            self.mac_step("verify universal binary", False)
        self.env["ARCHES"] = "arm64 x86_64 arm64e i386"
        self.mac_step("verify universal binary")

    def test_metadata_resource_drift_and_missing_leaves_fail_unsigned_validation(self):
        self.build()
        for relative in (*native.FILES[:-1], *native.PRESERVED):
            path = self.checkout / relative
            raw = path.read_bytes()
            for replacement in (None, b"", b"drift"):
                if replacement == b"drift" and relative in (*native.PRESERVED, native.FILES[0]):
                    continue
                with self.subTest(path=relative, replacement=replacement):
                    if replacement is None:
                        path.unlink()
                    else:
                        path.write_bytes(replacement)
                    self.mac_step("verify universal binary", False)
                    path.write_bytes(raw)
        self.assertFalse((self.checkout / native.FILES[-1]).exists())
        self.mac_step("verify universal binary")

    def test_every_credential_native_sign_notary_staple_failure_prevents_publication(self):
        cases = [{"FAIL_TOOL": tool} for tool in (
            "python3", "base64", "security", "xcrun", "xcodebuild", "lipo",
            "codesign", "ditto", "hdiutil",
        )] + [
            {"FAIL_PREFLIGHT": "1"}, {"MISSING_IDENTITY": "1"}, {"FAIL_VERIFY": "1"},
            {"STALE_BUILD": "1"}, {"ARCHES": "arm64e x86_64"},
            {"NOTARY_EXIT": "5", "NOTARY_STATUS": "Accepted"},
            {"NOTARY_STATUS": "Invalid"}, {"NOTARY_STATUS": ""},
            {"NOTARY_JSON": "not json"}, {"NOTARY_JSON": "[]"}, {"NOTARY_JSON": "{}"},
            {"STAPLE_EXIT": "8"},
            *({"NOTARY_JSON": value} for value in (
                '{"status":"Invalid","status":"Accepted"}',
                '{"status":"Accepted","extra":{"id":1,"id":2}}',
                '{"status":"Accepted","extra":NaN}', '{"status":"Accepted","extra":Infinity}',
                '{"status":"Accepted","extra":-Infinity}', '{"status":"Accepted","extra":1e999}',
            )),
        ]
        original_env = dict(self.env)
        for case in cases:
            with self.subTest(case=case):
                self.env = {**original_env, **case}
                self.log.unlink(missing_ok=True)
                for suffix in ("zip", "dmg"):
                    (self.checkout / f"Activate-{self.env['VERSION']}.{suffix}").unlink(missing_ok=True)
                result = self.pipeline()
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertFalse(any("publish" in call for call in self.calls()))


class WorkflowContractTests(unittest.TestCase):
    def test_exact_package_leaf_inventory_has_no_dependency_default_or_symlink_exceptions(self):
        prefix = "test/Plugins/activate.bundle/Contents/"
        self.assertEqual(set(map(str, native.PACKAGE_FILES)), {
            prefix + relative for relative in (
                "CodeResources", "Info.plist", "MacOS/activate", "QuickLook/Thumbnail.png",
                "Resources/English.lproj/InfoPlist.strings", "Resources/constants.xlf",
                "Resources/manifest.json", "Windows64/activate.4DX",
                "_CodeSignature/CodeResources",
            )
        })
        self.assertEqual(str(native.DOWNLOAD), "winbuild/activate.4DX")
        self.assertEqual(native.DIRECTORIES, (Path("test/Plugins/Activate.build"),))
        self.assertEqual(native.XCODE_DATA, Path("test/Plugins/XCBuildData"))
        self.assertEqual(set(map(str, native.EMPTY_DIRECTORIES)), {
            "test/Plugins/ExplicitPrecompiledModules",
            "test/Plugins/SwiftExplicitPrecompiledModules",
            "test/Plugins/EagerLinkingTBDs/Default",
        })

    def test_exact_two_manual_workflows_immutable_checkouts_inputs_and_crossref_lock(self):
        workflows = {path.name: yaml.load(path.read_text(), Loader=yaml.BaseLoader)
                     for path in WORKFLOW.parent.glob("*.yml")}
        self.assertEqual(set(workflows), {"release.yml", "bump-version.yml"})
        build, bump = workflows["release.yml"], workflows["bump-version.yml"]
        self.assertEqual(build["name"], "Build")
        self.assertEqual(build["on"], {"workflow_dispatch": ""})
        self.assertEqual(bump["name"], "Bump version")
        self.assertEqual(set(bump["on"]), {"workflow_dispatch"})
        inputs = bump["on"]["workflow_dispatch"]["inputs"]
        self.assertEqual(set(inputs), {"mode"})
        self.assertEqual(inputs["mode"]["type"], "choice")
        self.assertEqual(inputs["mode"]["options"], ["patch", "minor", "major"])
        self.assertEqual(inputs["mode"]["default"], "patch")
        self.assertEqual(inputs["mode"]["required"], "true")
        self.assertEqual(build["concurrency"],
                         {"group": "release-publication", "cancel-in-progress": "false"})
        self.assertNotEqual(bump["concurrency"]["group"], build["concurrency"]["group"])
        before = yaml.load(original(".github/workflows/release.yml"), Loader=yaml.BaseLoader)
        self.assertEqual(list(build["jobs"]), list(before["jobs"]))
        for name, job in build["jobs"].items():
            self.assertEqual(job["runs-on"], before["jobs"][name]["runs-on"])
            self.assertEqual(job.get("needs"), before["jobs"][name].get("needs"))
        for workflow in workflows.values():
            for job in workflow["jobs"].values():
                self.assertNotIn("if", job)
                checkouts = [s for s in job["steps"] if s.get("uses", "").startswith("actions/checkout@")]
                self.assertEqual(len(checkouts), 1)
                self.assertEqual(checkouts[0]["with"]["ref"], "${{ github.sha }}")
                for step in job["steps"]:
                    self.assertNotIn("if", step)
                    self.assertNotIn("${{", step.get("run", ""))
        for forbidden in ("inputs.", "github.ref", "softprops", "dispatches", "bump.py"):
            self.assertNotIn(forbidden, WORKFLOW.read_text())
        self.assertEqual([s["run"] for s in bump["jobs"]["bump"]["steps"] if "run" in s], [
            'python3 .github/scripts/bump.py "$MODE" --sha "$EVENT_SHA" --ref "$EVENT_REF"'
        ])

    def test_exact_original_cmd_setup_and_native_configuration_preserved(self):
        before = yaml.load(original(".github/workflows/release.yml"), Loader=yaml.BaseLoader)
        after = yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader)
        get = lambda steps, name: next(s for s in steps if s.get("name") == name)
        for name in ("build x64", "setup MSBuild"):
            self.assertEqual(get(after["jobs"]["build-windows"]["steps"], name),
                             get(before["jobs"]["build-windows"]["steps"], name))
        self.assertEqual(after["env"]["PRODUCT_NAME"], "Activate")
        self.assertEqual(after["env"]["MACOS_DEPLOYMENT_TARGET"], "11.0")
        self.assertEqual(native.PRODUCT, "activate")
        project = ET.fromstring(original("Activate.vcxproj"))
        ns = {"m": "http://schemas.microsoft.com/developer/msbuild/2003"}
        condition = "'$(Configuration)|$(Platform)'=='Release|x64'"
        selected = lambda field: next(x.text for x in project.findall(".//m:" + field, ns)
                                      if x.get("Condition") == condition)
        self.assertEqual(selected("OutDir"), "$(ProjectDir)test\\plugins\\$(ProjectName).bundle\\contents\\windows64\\")
        self.assertEqual(selected("IntDir"), "$(SolutionDir)Objs\\$(Configuration)\\")
        self.assertEqual(selected("TargetExt"), ".4DX")
        sln = original("Activate.sln").decode("utf-8-sig")
        self.assertIn('"activate", "activate.vcxproj"', sln)
        normalize = lambda data: re.sub(
            rb"((?:MARKETING_VERSION|CURRENT_PROJECT_VERSION)\s*=\s*)[0-9.]+;",
            rb"\g<1>VERSION;", data)
        self.assertEqual(normalize((ROOT / source.PROJECT).read_bytes()),
                         normalize(original(source.PROJECT)))
        for path in ("Activate.vcxproj", "Activate.sln", "manifest.json", "constants.xlf",
                     *map(str, native.PACKAGE_FILES)):
            self.assertEqual((ROOT / path).read_bytes(), original(path), path)

    def test_preflight_before_any_native_and_publication_last(self):
        jobs = yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader)["jobs"]
        for job in jobs.values():
            runs = [s for s in job["steps"] if "run" in s]
            self.assertIn("release.py preflight", runs[0]["run"])
            self.assertEqual(runs[0]["env"]["GH_TOKEN"], "${{ github.token }}")
        last = jobs["build-macos"]["steps"][-1]
        self.assertIn("release.py publish", last["run"])
        self.assertEqual(last["env"]["GH_TOKEN"], "${{ github.token }}")
