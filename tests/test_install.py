"""Tests for the install CLI."""

from ninja_assets.cli.install import (
    install, uninstall, _inject_hook, _remove_hook, write_build_stamp,
    HOOK_START, HOOK_END,
)


class TestInjectHook:
    def test_creates_usersetup_if_missing(self, tmp_path):
        setup = tmp_path / "userSetup.py"
        _inject_hook(setup)
        assert setup.exists()
        content = setup.read_text()
        assert HOOK_START in content
        assert "plugin.initialize()" in content

    def test_appends_to_existing(self, tmp_path):
        setup = tmp_path / "userSetup.py"
        setup.write_text("# my existing stuff\nprint('hello')\n")
        _inject_hook(setup)
        content = setup.read_text()
        assert "my existing stuff" in content
        assert HOOK_START in content

    def test_idempotent(self, tmp_path):
        setup = tmp_path / "userSetup.py"
        _inject_hook(setup)
        content1 = setup.read_text()
        _inject_hook(setup)
        content2 = setup.read_text()
        assert content1 == content2

    def test_remove_hook(self, tmp_path):
        setup = tmp_path / "userSetup.py"
        setup.write_text("# before\n")
        _inject_hook(setup)
        assert HOOK_START in setup.read_text()
        _remove_hook(setup)
        content = setup.read_text()
        assert HOOK_START not in content
        assert HOOK_END not in content
        assert "before" in content


class TestInstallUninstall:
    def test_install_symlink(self, tmp_path):
        scripts_dir = tmp_path / "scripts"
        install(scripts_dir, use_symlink=True)

        target = scripts_dir / "ninja_assets"
        assert target.exists()
        assert target.is_symlink()
        assert (scripts_dir / "userSetup.py").exists()

    def test_install_copy(self, tmp_path):
        scripts_dir = tmp_path / "scripts"
        install(scripts_dir, use_symlink=False)

        target = scripts_dir / "ninja_assets"
        assert target.exists()
        assert target.is_dir()
        assert not target.is_symlink()
        # Should have copied actual files
        assert (target / "__init__.py").exists()
        # And stamped the build so upgrades can be detected
        assert (target / "_build_stamp.txt").exists()
        assert (target / "_build_stamp.txt").read_text().strip()

    def test_uninstall_removes_symlink(self, tmp_path):
        scripts_dir = tmp_path / "scripts"
        install(scripts_dir, use_symlink=True)
        assert (scripts_dir / "ninja_assets").exists()

        uninstall(scripts_dir)
        assert not (scripts_dir / "ninja_assets").exists()
        content = (scripts_dir / "userSetup.py").read_text()
        assert HOOK_START not in content

    def test_reinstall_replaces(self, tmp_path):
        scripts_dir = tmp_path / "scripts"
        install(scripts_dir, use_symlink=False)
        install(scripts_dir, use_symlink=True)

        target = scripts_dir / "ninja_assets"
        assert target.is_symlink()


class TestBuildStamp:
    def test_writes_file(self, tmp_path):
        value = write_build_stamp(tmp_path)
        stamp = tmp_path / "_build_stamp.txt"
        assert stamp.exists()
        assert stamp.read_text() == value
        assert value

    def test_unique_per_call(self, tmp_path):
        a = write_build_stamp(tmp_path)
        b = write_build_stamp(tmp_path)
        assert a != b
