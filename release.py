"""Helper for updating version variables from toml file."""

import re
import sys
from pathlib import Path


TOML_PATH = Path(Path(__file__).parent, "pyproject.toml")
BROKER_PATH = Path(Path(__file__).parent, "broker/__init__.py")


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


def main() -> int:
    update_python_version(get_current_version_from_toml())
    return 0


if __name__ == "__main__":
    sys.exit(main())
