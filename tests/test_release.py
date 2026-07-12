import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import release


def test_get_current_version_from_toml(tmp_path, monkeypatch):
    toml_path = tmp_path / "pyproject.toml"
    toml_path.write_text(
        """
[project]
version = "2.4.6"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(release, "TOML_PATH", toml_path)

    assert release.get_current_version_from_toml() == (2, 4, 6)
    assert release.get_current_version_string() == "2.4.6"


def test_update_versions_syncs_targets(tmp_path, monkeypatch):
    yaml_path = tmp_path / "package.yaml"
    private_broker_path = tmp_path / "broker/private/broker.py"
    public_init_path = tmp_path / "broker/__init__.py"

    private_broker_path.parent.mkdir(parents=True, exist_ok=True)
    public_init_path.parent.mkdir(parents=True, exist_ok=True)

    yaml_path.write_text("name: broker\nversion: 1.2.3\n", encoding="utf-8")
    private_broker_path.write_text(
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
    public_init_path.write_text(
        "\n".join(
            [
                "_instance = object()",
                "paused = None",
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
    monkeypatch.setattr(release, "PRIVATE_BROKER_PATH", private_broker_path)
    monkeypatch.setattr(release, "PUBLIC_INIT_PATH", public_init_path)

    release.update_versions((4, 5, 6))

    assert "version: 4.5.6" in yaml_path.read_text(encoding="utf-8")
    assert "version_major = 4" in private_broker_path.read_text(encoding="utf-8")
    assert "version_minor = 5" in private_broker_path.read_text(encoding="utf-8")
    assert "version_patch = 6" in private_broker_path.read_text(encoding="utf-8")
    assert "version_major = 4" in public_init_path.read_text(encoding="utf-8")
    assert "version_minor = 5" in public_init_path.read_text(encoding="utf-8")
    assert "version_patch = 6" in public_init_path.read_text(encoding="utf-8")


def test_update_python_version_preserves_indentation(tmp_path, monkeypatch):
    private_broker_path = tmp_path / "broker/private/broker.py"
    private_broker_path.parent.mkdir(parents=True, exist_ok=True)
    private_broker_path.write_text(
        "\n".join(
            [
                "class Broker:",
                "    version_major = 1",
                "    version_minor = 2",
                "    version_patch = 3",
                '    __version__ = f"{version_major}.{version_minor}.{version_patch}"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(release, "PRIVATE_BROKER_PATH", private_broker_path)

    release.update_python_version((7, 8, 9))

    content = private_broker_path.read_text(encoding="utf-8")
    assert "    version_major = 7" in content
    assert "    version_minor = 8" in content
    assert "    version_patch = 9" in content
