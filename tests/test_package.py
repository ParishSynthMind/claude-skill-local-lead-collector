import zipfile

from conftest import ROOT
import importlib.util

spec = importlib.util.spec_from_file_location("package_skill", ROOT / "tools" / "package_skill.py")
package_skill = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package_skill)


def test_zip_has_skill_folder_at_root(tmp_path):
    out = package_skill.build(tmp_path / "skill.zip")
    names = zipfile.ZipFile(out).namelist()
    assert "local-lead-collector/SKILL.md" in names
    assert all(n.startswith("local-lead-collector/") for n in names)
    assert not any("__pycache__" in n or n.endswith(".pyc") for n in names)
