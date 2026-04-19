"""Helper for updating version variables from toml file."""

import re
import sys
from pathlib import Path


TOML_PATH = Path(Path(__file__).parent, "pyproject.toml")
BROKER_PATH = Path(Path(__file__).parent, "broker/private/broker.py")
YAML_PATH = Path(Path(__file__).parent, "package.yaml")


def parse_version(version_str: str) -> tuple[int, int, int]:
    """Parse a version string into major, minor, patch tuple."""
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", version_str.strip("\"'"))
    if not match:
        raise ValueError(f"Invalid version format: {version_str}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def get_current_version_from_toml() -> tuple[int, int, int]:
    """Extract current version from TOML file."""
    content = TOML_PATH.read_text()
    match = re.search(r'version\s*=\s*["\'](\d+\.\d+\.\d+)["\']', content)

    if not match:
        raise ValueError("No version field found in TOML file")

    return parse_version(match.group(1))


def update_python_version(new_version: tuple[int, int, int]) -> None:
    """Update version constants in Python file."""
    content = BROKER_PATH.read_text(encoding="utf-8")

    major, minor, patch = new_version

    # Replace each version constant
    replacements = [
        (r"version_major\s*=\s*\d+", f"version_major = {major}"),
        (r"version_minor\s*=\s*\d+", f"version_minor = {minor}"),
        (r"version_patch\s*=\s*\d+", f"version_patch = {patch}"),
    ]

    new_content = content
    for pattern, replacement in replacements:
        new_content, count = re.subn(pattern, replacement, new_content)
        if count == 0:
            raise ValueError(f"Pattern not found: {pattern}")

    BROKER_PATH.write_text(new_content)
    print(f"Updated {BROKER_PATH}:")
    print(f"  version_major = {major}")
    print(f"  version_minor = {minor}")
    print(f"  version_patch = {patch}")


def update_yaml_version(new_version: tuple[int, int, int]) -> None:
    """Update version field in package.yaml file."""
    content = YAML_PATH.read_text(encoding="utf-8")
    version_str = ".".join(str(p) for p in new_version)

    new_content, count = re.subn(
        r"^(version\s*:\s*)\S+",
        rf"\g<1>{version_str}",
        content,
        flags=re.MULTILINE,
    )

    if count == 0:
        raise ValueError("No version field found in package.yaml")

    YAML_PATH.write_text(new_content, encoding="utf-8")
    print(f"Updated {YAML_PATH}:")
    print(f"  version: {version_str}")


def main() -> int:
    new_version = get_current_version_from_toml()
    update_python_version(new_version)
    update_yaml_version(new_version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
