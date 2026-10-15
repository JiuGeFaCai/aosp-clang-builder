from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


INSTALLER = Path(__file__).parents[1] / "scripts/install-toolchain.sh"


class InstallToolchainTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.toolchain = self.root / "moved toolchain" / "clang-r487747c"
        (self.toolchain / "bin").mkdir(parents=True)
        self.installer = self.toolchain / "install.sh"
        shutil.copyfile(INSTALLER, self.installer)
        self.installer.chmod(0o755)
        compiler = self.toolchain / "bin/clang"
        compiler.write_text("#!/bin/sh\nprintf 'test toolchain\\n'\n")
        compiler.chmod(0o755)
        (self.toolchain / "bin/clang++").symlink_to("clang")
        self.prefix = self.root / "command links"

    def install(self):
        return subprocess.run(
            [self.installer, "--prefix", self.prefix], cwd=self.root,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )

    def test_installs_commands_with_spaces_and_preserves_aliases(self):
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stdout)
        for name in ("clang", "clang++"):
            installed = self.prefix / "bin" / name
            self.assertTrue(installed.is_symlink())
            self.assertEqual(installed.readlink(), self.toolchain / "bin" / name)
            self.assertEqual(subprocess.check_output([installed], text=True), "test toolchain\n")

    def test_reinstall_is_idempotent(self):
        for _ in range(2):
            result = self.install()
            self.assertEqual(result.returncode, 0, result.stdout)

    def test_conflict_does_not_overwrite_or_partially_install(self):
        (self.prefix / "bin").mkdir(parents=True)
        existing = self.prefix / "bin/clang++"
        existing.write_text("existing installation\n")
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Already exists:", result.stdout)
        self.assertEqual(existing.read_text(), "existing installation\n")
        self.assertFalse((self.prefix / "bin/clang").exists())


if __name__ == "__main__":
    unittest.main()
