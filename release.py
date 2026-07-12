"""Helper for syncing version files from ``pyproject.toml``."""

import re
import sys
from pathlib import Path


ROOT = Path(__file__).parent
TOML_PATH = ROOT / "pyproject.toml"
PACKAGE_YAML_PATH = ROOT / "package.yaml"
PRIVATE_BROKER_PATH = ROOT / "broker/private/broker.py"
PUBLIC_INIT_PATH = ROOT / "broker/__init__.py"

VERSION_PATTERN = re.compile(r'^version\s*=\s*["\'](\d+\.\d+\.\d+)["\']\s*$', re.M)


def parse_version(version_str: str) -> tuple[int, int, int]:
    """Parse a version string into ``major, minor, patch``."""
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version_str.strip("\"'"))
    if not match:
        raise ValueError(f"Invalid version format: {version_str}")
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def format_version(version: tuple[int, int, int]) -> str:
    return ".".join(str(part) for part in version)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def get_current_version_from_toml() -> tuple[int, int, int]:
    """Extract the current version from ``pyproject.toml``."""
    match = VERSION_PATTERN.search(read_text(TOML_PATH))
    if not match:
        raise ValueError("No version field found in pyproject.toml")
    return parse_version(match.group(1))


def get_current_version_string() -> str:
    """Return the version currently recorded in ``pyproject.toml``."""
    return format_version(get_current_version_from_toml())


def replace_version_fields(path: Path, replacements: list[tuple[str, str]]) -> None:
    content = read_text(path)
    new_content = content

    for pattern, replacement in replacements:
        new_content, count = re.subn(pattern, replacement, new_content, flags=re.M)
        if count == 0:
            raise ValueError(f"Pattern not found in {path}: {pattern}")

    write_text(path, new_content)


def update_python_version(new_version: tuple[int, int, int]) -> None:
    """Update version constants in Python files."""
    major, minor, patch = new_version
    replacements = [
        (r"^version_major\s*=\s*\d+\s*$", f"version_major = {major}"),
        (r"^version_minor\s*=\s*\d+\s*$", f"version_minor = {minor}"),
        (r"^version_patch\s*=\s*\d+\s*$", f"version_patch = {patch}"),
    ]

    for path in (PRIVATE_BROKER_PATH, PUBLIC_INIT_PATH):
        replace_version_fields(path, replacements)
        print(f"Updated {path}:")
        print(f"  version_major = {major}")
        print(f"  version_minor = {minor}")
        print(f"  version_patch = {patch}")


def update_yaml_version(new_version: tuple[int, int, int]) -> None:
    """Update version field in package.yaml file."""
    content = read_text(PACKAGE_YAML_PATH)
    version_str = format_version(new_version)

    new_content, count = re.subn(
        r"^(version\s*:\s*)\S+",
        rf"\g<1>{version_str}",
        content,
        flags=re.MULTILINE,
    )

    if count == 0:
        raise ValueError("No version field found in package.yaml")

    write_text(PACKAGE_YAML_PATH, new_content)
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

    current_version = get_current_version_from_toml()
    update_versions(current_version)
    print(f"Synced version: {format_version(current_version)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
