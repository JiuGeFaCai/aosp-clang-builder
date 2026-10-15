import importlib.util
import json
from pathlib import Path
import tempfile
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("builder", Path(__file__).parents[1] / "scripts/build.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class PatchSelectionTests(unittest.TestCase):
    def test_revision_boundaries_and_patch_order(self):
        entries = [
            {"rel_patch_path": "first.patch", "version_range": {"from": 100, "until": 200}},
            {"rel_patch_path": "expired.patch", "version_range": {"from": 1, "until": 100}},
            {"rel_patch_path": "later.patch", "version_range": {"from": 101, "until": None}},
            {"rel_patch_path": "last.patch", "version_range": {"from": None, "until": None}},
        ]
        self.assertEqual(
            [item["rel_patch_path"] for item in builder.select_patches(entries, 100)],
            ["first.patch", "last.patch"],
        )
        self.assertEqual(
            [item["rel_patch_path"] for item in builder.select_patches(entries, 200)],
            ["later.patch", "last.patch"],
        )

    def test_patch_path_must_stay_in_patch_directory(self):
        for name in ("/tmp/a.patch", "../a.patch", "cherry/../../a.patch"):
            with self.subTest(name=name), self.assertRaises(builder.BuildError):
                builder.select_patches([{"rel_patch_path": name}], 100)

    def test_patches_apply_inside_an_outer_actions_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "--quiet", root], check=True)
            source = root / ".build/sources/llvm"
            source.mkdir(parents=True)
            (source / "file.txt").write_text("before\n")
            patches = root / "patches"
            patches.mkdir()
            (patches / "change.patch").write_text(
                "diff --git a/file.txt b/file.txt\n"
                "--- a/file.txt\n+++ b/file.txt\n"
                "@@ -1 +1 @@\n-before\n+after\n"
            )
            applied = builder.apply_patchset(source, patches, [{"rel_patch_path": "change.patch"}])
            self.assertEqual((source / "file.txt").read_text(), "after\n")
            self.assertEqual(len(applied), 1)


class RevisionTests(unittest.TestCase):
    def test_resolved_variant_is_not_mislabeled(self):
        self.assertEqual(builder.effective_revision("r522817", "r522817d"), "r522817d")
        self.assertEqual(builder.effective_revision("r536225b", "r536225"), "r536225b")
        with self.assertRaises(builder.BuildError):
            builder.effective_revision("r522817b", "r522817d")
        with self.assertRaises(builder.BuildError):
            builder.effective_revision("r536225", "r547379")

    def test_suffix_does_not_silently_select_a_different_patch_set(self):
        with self.assertRaises(builder.BuildError):
            builder.toolchain_revision("r536225b", "")
        with patch.object(builder, "resolve_ref", return_value="a" * 40) as resolve:
            self.assertEqual(builder.toolchain_revision("r536225b", "specific-manifest-commit"), "a" * 40)
            resolve.assert_called_once_with(builder.TOOLCHAIN_REPO, "specific-manifest-commit")

    def test_default_r536225_is_pinned(self):
        with patch.object(builder, "resolve_ref") as resolve:
            self.assertEqual(
                builder.toolchain_revision("r536225", ""),
                "43ef7af1325b43e13d926d74a89741d4ace5fcf8",
            )
            resolve.assert_not_called()

    def test_r487747c_prepares_without_explicit_refs(self):
        def source_archive(repo, sha, destination, cache):
            destination.mkdir(parents=True)
            if repo == builder.TOOLCHAIN_REPO:
                self.assertEqual(sha, "8443a75fcd5c80245b194f6510b98a11098fe7fe")
                # Metadata from r487747c's manifest_10087095.xml checkout.
                (destination / "android_version.py").write_text(
                    "_svn_revision = 'r487747c'\n"
                    "_git_sha = 'c4c5e79dd4b4c78eee7cffd9b0d7394b5bedcf12'\n"
                    "_patch_level = '2'\n"
                )
                (destination / "patches").mkdir()
                (destination / "patches/PATCHES.json").write_text("[]\n")
            else:
                self.assertEqual(repo, builder.LLVM_REPO)
                self.assertEqual(sha, "c4c5e79dd4b4c78eee7cffd9b0d7394b5bedcf12")

        with tempfile.TemporaryDirectory() as directory:
            for requested in ("r487747c", "clang-r487747c"):
                with self.subTest(requested=requested):
                    work = Path(directory) / requested
                    work.mkdir()
                    args = SimpleNamespace(clang_revision=requested, toolchain_ref="", llvm_ref="")
                    with patch.object(builder, "source_archive", side_effect=source_archive), \
                            patch.object(builder, "github_json") as github:
                        builder.prepare(args, work)
                        github.assert_not_called()
                    metadata = json.loads((work / "source-lock.json").read_text())
                    self.assertEqual(metadata["clang_revision"], "r487747c")
                    self.assertEqual(metadata["svn_revision"], 487747)
                    self.assertEqual(metadata["aosp_patch_level"], "2")
                    self.assertFalse(metadata["custom_llvm_base"])

    def test_explicit_ref_overrides_r487747c_preset(self):
        with patch.object(builder, "resolve_ref", return_value="b" * 40) as resolve:
            self.assertEqual(builder.toolchain_revision("r487747c", "custom-ref"), "b" * 40)
            resolve.assert_called_once_with(builder.TOOLCHAIN_REPO, "custom-ref")

    def test_release_branch_fallback(self):
        for status in (404, 422):
            with self.subTest(status=status):
                missing = builder.urllib.error.HTTPError("url", status, "missing", {}, None)
                with patch.object(builder, "resolve_ref", side_effect=[missing, "a" * 40]) as resolve:
                    self.assertEqual(builder.toolchain_revision("r522817", ""), "a" * 40)
                    self.assertEqual(
                        [call.args[1] for call in resolve.call_args_list],
                        ["llvm-r522817-release", "llvm-r522817"],
                    )

    def test_version_file_is_read_without_executing_it(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "android_version.py"
            source.write_text(
                "_svn_revision = 'r536225'\n"
                "_git_sha: str = '" + "a" * 40 + "'\n"
                "_patch_level = '1'\n"
                "raise RuntimeError('must not execute')\n"
            )
            constants = builder.version_constants(source)
            self.assertEqual(constants["_svn_revision"], "r536225")
            self.assertEqual(constants["_patch_level"], "1")


if __name__ == "__main__":
    unittest.main()
