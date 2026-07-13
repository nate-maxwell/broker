"""Helper for syncing version files from ``broker/__init__.py``."""

import re
import sys
from pathlib import Path


ROOT = Path(__file__).parent
PACKAGE_YAML_PATH = ROOT / "package.yaml"
BROKER_INIT_PATH = ROOT / "broker/__init__.py"

VERSION_MAJOR_PATTERN = re.compile(r"^version_major\s*=\s*(\d+)\s*$", re.M)
VERSION_MINOR_PATTERN = re.compile(r"^version_minor\s*=\s*(\d+)\s*$", re.M)
VERSION_PATCH_PATTERN = re.compile(r"^version_patch\s*=\s*(\d+)\s*$", re.M)


def parse_version(version_str: str) -> tuple[int, int, int]:
    """Parse a version string into ``major, minor, patch``."""
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version_str.strip("\"'"))
    if not match:
        raise ValueError(f"Invalid version format: {version_str}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def format_version(version: tuple[int, int, int]) -> str:
    return ".".join(str(part) for part in version)


def get_current_version_from_python() -> tuple[int, int, int]:
    """Extract the current version from ``broker/__init__.py``."""
    content = BROKER_INIT_PATH.read_text(encoding="utf-8")

    major_match = VERSION_MAJOR_PATTERN.search(content)
    minor_match = VERSION_MINOR_PATTERN.search(content)
    patch_match = VERSION_PATCH_PATTERN.search(content)
    if not (major_match and minor_match and patch_match):
        raise ValueError("No version fields found in broker/__init__.py")

    return parse_version(
        f"{major_match.group(1)}.{minor_match.group(1)}.{patch_match.group(1)}"
    )


def get_current_version_string() -> str:
    """Return the version currently recorded in ``broker/__init__.py``."""
    return format_version(get_current_version_from_python())


def replace_version_fields(path: Path, replacements: list[tuple[str, str]]) -> None:
    content = path.read_text(encoding="utf-8")
    new_content = content

    for pattern, replacement in replacements:
        new_content, count = re.subn(pattern, replacement, new_content, flags=re.M)
        if count == 0:
            raise ValueError(f"Pattern not found in {path}: {pattern}")

    path.write_text(new_content, encoding="utf-8")


def update_python_version(new_version: tuple[int, int, int]) -> None:
    """Update version constants in Python files."""
    major, minor, patch = new_version
    replacements = [
        (r"^(\s*)version_major\s*=\s*\d+\s*$", rf"\1version_major = {major}"),
        (r"^(\s*)version_minor\s*=\s*\d+\s*$", rf"\1version_minor = {minor}"),
        (r"^(\s*)version_patch\s*=\s*\d+\s*$", rf"\1version_patch = {patch}"),
    ]

    replace_version_fields(BROKER_INIT_PATH, replacements)
    print(f"Updated {BROKER_INIT_PATH}:")
    print(f"  version_major = {major}")
    print(f"  version_minor = {minor}")
    print(f"  version_patch = {patch}")


def update_yaml_version(new_version: tuple[int, int, int]) -> None:
    """Update version field in package.yaml file."""
    content = PACKAGE_YAML_PATH.read_text(encoding="utf-8")
    version_str = format_version(new_version)

    new_content, count = re.subn(
        r"^(version\s*:\s*)\S+",
        rf"\g<1>{version_str}",
        content,
        flags=re.MULTILINE,
    )

    if count == 0:
        raise ValueError("No version field found in package.yaml")

    PACKAGE_YAML_PATH.write_text(new_content, encoding="utf-8")
    print(f"Updated {PACKAGE_YAML_PATH}:")
    print(f"  version: {version_str}")


def update_versions(new_version: tuple[int, int, int]) -> None:
    update_yaml_version(new_version)
    update_python_version(new_version)


def main() -> int:
    args = sys.argv[1:]
    if "--print-version" in args:
        print(get_current_version_string())
        return 0

    current_version = get_current_version_from_python()
    update_versions(current_version)
    print(f"Synced version: {format_version(current_version)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
