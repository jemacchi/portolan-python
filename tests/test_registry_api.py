"""Registry API tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from portolan import download_registry_catalog, load_registry_entries

pytestmark = pytest.mark.unit


def _collection(collection_id: str, asset: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "Collection",
        "stac_version": "1.1.0",
        "id": collection_id,
        "description": f"{collection_id} description",
        "license": "CC-BY-4.0",
        "extent": {
            "spatial": {"bbox": [[-71.0, -35.0, -70.0, -34.0]]},
            "temporal": {"interval": [[None, None]]},
        },
        "links": [],
        "assets": {"data": asset},
    }


def test_load_registry_entries_filters_to_valid_children() -> None:
    registry = {
        "links": [
            {
                "rel": "child",
                "href": "https://example.test/a/catalog.json",
                "title": "A",
                "portolan_registry:id": "catalog-a",
                "portolan_registry:status": "valid",
            },
            {
                "rel": "child",
                "href": "https://example.test/b/catalog.json",
                "portolan_registry:id": "catalog-b",
                "portolan_registry:status": "stale",
            },
        ]
    }

    entries = load_registry_entries(
        "https://registry.test/catalogs.json", fetch_json=lambda url: registry
    )

    assert [(entry.id, entry.url, entry.title, entry.status) for entry in entries] == [
        ("catalog-a", "https://example.test/a/catalog.json", "A", "valid")
    ]


def test_load_registry_entries_supports_catalog_ids_include_stale_and_limit() -> None:
    registry = {
        "links": [
            {
                "rel": "child",
                "href": "https://example.test/a/catalog.json",
                "portolan_registry:id": "catalog-a",
                "portolan_registry:status": "valid",
            },
            {
                "rel": "child",
                "href": "https://example.test/b/catalog.json",
                "portolan_registry:id": "catalog-b",
                "portolan_registry:status": "stale",
            },
            {
                "rel": "child",
                "href": "https://example.test/c/catalog.json",
                "portolan_registry:id": "catalog-c",
                "portolan_registry:status": "valid",
            },
            {"rel": "item", "href": "https://example.test/ignored/item.json"},
            {"rel": "child", "href": 100, "portolan_registry:id": "ignored"},
        ]
    }

    entries = load_registry_entries(
        "https://registry.test/catalogs.json",
        fetch_json=lambda url: registry,
        catalog_ids={"catalog-b", "catalog-c"},
        include_stale=True,
        limit=1,
    )

    assert [(entry.id, entry.status) for entry in entries] == [("catalog-b", "stale")]


def test_download_registry_catalog_writes_snapshot_with_absolute_asset_hrefs(
    tmp_path: Path,
) -> None:
    responses = {
        "https://example.test/demo/catalog.json": {
            "type": "Catalog",
            "id": "demo",
            "links": [
                {"rel": "child", "href": "./roads/collection.json", "type": "application/json"}
            ],
        },
        "https://example.test/demo/roads/collection.json": _collection(
            "roads",
            {
                "href": "./roads.parquet",
                "type": "application/vnd.apache.parquet",
                "roles": ["data"],
            },
        ),
    }

    catalog_root = download_registry_catalog(
        "https://example.test/demo/catalog.json",
        tmp_path,
        fetch_json=lambda url: responses[url],
    )

    assert catalog_root == tmp_path / "demo"
    catalog = json.loads((catalog_root / "catalog.json").read_text(encoding="utf-8"))
    collection = json.loads(
        (catalog_root / "roads" / "collection.json").read_text(encoding="utf-8")
    )
    assert catalog["links"][0]["href"] == "./roads/collection.json"
    assert collection["assets"]["data"]["href"] == "https://example.test/demo/roads/roads.parquet"


def test_download_registry_catalog_recurses_nested_catalogs_and_uses_fallback_id(
    tmp_path: Path,
) -> None:
    responses = {
        "https://example.test/nested/catalog.json": {
            "type": "Catalog",
            "links": [{"rel": "child", "href": "./theme/catalog.json"}],
        },
        "https://example.test/nested/theme/catalog.json": {
            "type": "Catalog",
            "id": "theme",
            "links": [{"rel": "child", "href": "./roads/collection.json"}],
        },
        "https://example.test/nested/theme/roads/collection.json": _collection(
            "roads",
            {
                "href": "../roads.parquet",
                "type": "application/vnd.apache.parquet",
                "roles": ["data"],
            },
        ),
    }

    catalog_root = download_registry_catalog(
        "https://example.test/nested/catalog.json",
        tmp_path,
        fetch_json=lambda url: responses[url],
    )

    assert catalog_root == tmp_path / "nested"
    assert (catalog_root / "catalog.json").exists()
    assert (catalog_root / "theme" / "catalog.json").exists()
    collection = json.loads(
        (catalog_root / "theme" / "roads" / "collection.json").read_text(encoding="utf-8")
    )
    assert collection["assets"]["data"]["href"] == "https://example.test/nested/theme/roads.parquet"
