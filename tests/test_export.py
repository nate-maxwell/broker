"""
Unit tests for broker export functionality.

Tests verify that the export method correctly writes broker state to files
in JSON format.
"""

import json
from pathlib import Path

import broker


def test_export_creates_valid_json_file(tmp_path: Path) -> None:
    """Test that export creates a valid JSON file with correct content."""
    broker.clear()

    def handler1(data: str) -> None:
        pass

    async def handler2(data: str) -> None:
        pass

    broker.register_subscriber("test.event", handler1, priority=10)
    broker.register_subscriber("app.startup", handler2)

    output_file = tmp_path / "broker_export.json"
    broker.export(output_file)

    # File should exist
    assert output_file.exists()

    # Should be valid JSON
    with open(output_file) as f:
        data = json.load(f)

    # Content should match to_dict()
    assert data == broker.to_dict()

    # Should contain expected namespaces
    assert "test.event" in data
    assert "app.startup" in data


def test_export_with_string_and_path_types(tmp_path: Path) -> None:
    """Test that export accepts both string and Path objects."""
    broker.clear()

    def handler(data: str) -> None:
        pass

    broker.register_subscriber("test.event", handler)

    # Test with Path object
    path_file = tmp_path / "path_export.json"
    broker.export(path_file)
    assert path_file.exists()

    # Test with string
    string_file = str(tmp_path / "string_export.json")
    broker.export(string_file)
    assert Path(string_file).exists()


def test_export_includes_metadata(tmp_path: Path) -> None:
    """Test that export includes priority and async flags."""
    broker.clear()

    def sync_handler(data: str) -> None:
        pass

    async def async_handler(data: str) -> None:
        pass

    broker.register_subscriber("test.event", sync_handler, priority=10)
    broker.register_subscriber("test.event", async_handler, priority=5)

    output_file = tmp_path / "broker_export.json"
    broker.export(output_file)

    with open(output_file) as f:
        data = json.load(f)

    subscribers = data["test.event"]["subscribers"]

    # Verify metadata is included
    assert any("[priority=10]" in s for s in subscribers)
    assert any("[priority=5]" in s for s in subscribers)
    assert any("[async]" in s for s in subscribers)


def test_export_empty_broker(tmp_path: Path) -> None:
    """Test exporting an empty broker creates valid empty JSON."""
    broker.clear()

    output_file = tmp_path / "empty_broker.json"
    broker.export(output_file)

    assert output_file.exists()

    with open(output_file) as f:
        data = json.load(f)

    assert data == {}
