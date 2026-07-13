import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import release


def test_get_current_version_from_python(tmp_path, monkeypatch):
    broker_init_path = tmp_path / "broker/__init__.py"
    broker_init_path.parent.mkdir(parents=True, exist_ok=True)
    broker_init_path.write_text(
        "\n".join(
            [
                "version_major = 2",
                "version_minor = 4",
                "version_patch = 6",
                '__version__ = f"{version_major}.{version_minor}.{version_patch}"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(release, "BROKER_INIT_PATH", broker_init_path)

    assert release.get_current_version_from_python() == (2, 4, 6)
    assert release.get_current_version_string() == "2.4.6"


def test_update_versions_syncs_targets(tmp_path, monkeypatch):
    yaml_path = tmp_path / "package.yaml"
    broker_init_path = tmp_path / "broker/__init__.py"

    broker_init_path.parent.mkdir(parents=True, exist_ok=True)

    yaml_path.write_text("name: broker\nversion: 1.2.3\n", encoding="utf-8")
    broker_init_path.write_text(
        "\n".join(
            [
                "version_major = 1",
                "version_minor = 2",
                "version_patch = 3",
                '__version__ = f"{version_major}.{version_minor}.{version_patch}"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(release, "PACKAGE_YAML_PATH", yaml_path)
    monkeypatch.setattr(release, "BROKER_INIT_PATH", broker_init_path)

    release.update_versions((4, 5, 6))

    assert "version: 4.5.6" in yaml_path.read_text(encoding="utf-8")
    assert "version_major = 4" in broker_init_path.read_text(encoding="utf-8")
    assert "version_minor = 5" in broker_init_path.read_text(encoding="utf-8")
    assert "version_patch = 6" in broker_init_path.read_text(encoding="utf-8")


def test_update_python_version_preserves_indentation(tmp_path, monkeypatch):
    broker_init_path = tmp_path / "broker/__init__.py"
    broker_init_path.parent.mkdir(parents=True, exist_ok=True)
    broker_init_path.write_text(
        "\n".join(
            [
                "version_major = 1",
                "version_minor = 2",
                "version_patch = 3",
                '__version__ = f"{version_major}.{version_minor}.{version_patch}"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(release, "BROKER_INIT_PATH", broker_init_path)

    release.update_python_version((7, 8, 9))

    content = broker_init_path.read_text(encoding="utf-8")
    assert "version_major = 7" in content
    assert "version_minor = 8" in content
    assert "version_patch = 9" in content
