"""Catalog domain API tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from portolan import AssetFormat, Catalog, Collection, Validator

pytestmark = pytest.mark.unit


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def test_open_catalog_traverses_collections_items_and_assets(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "catalog.json",
        {
            "type": "Catalog",
            "stac_version": "1.1.0",
            "id": "demo",
            "description": "Demo catalog",
            "links": [
                {"rel": "child", "href": "./roads/collection.json", "type": "application/json"}
            ],
        },
    )
    _write_json(
        tmp_path / "roads" / "collection.json",
        {
            "type": "Collection",
            "stac_version": "1.1.0",
            "id": "roads",
            "description": "Roads",
            "license": "CC-BY-4.0",
            "extent": {
                "spatial": {"bbox": [[-71.0, -35.0, -70.0, -34.0]]},
                "temporal": {"interval": [[None, None]]},
            },
            "links": [{"rel": "item", "href": "./road-1/road-1.json"}],
            "assets": {
                "data": {
                    "href": "./roads.parquet",
                    "type": "application/vnd.apache.parquet",
                    "roles": ["data"],
                }
            },
        },
    )
    _write_json(
        tmp_path / "roads" / "road-1" / "road-1.json",
        {
            "type": "Feature",
            "stac_version": "1.1.0",
            "id": "road-1",
            "collection": "roads",
            "geometry": None,
            "bbox": [-71.0, -35.0, -70.0, -34.0],
            "properties": {"datetime": None},
            "links": [],
            "assets": {
                "data": {
                    "href": "./road-1.parquet",
                    "type": "application/vnd.apache.parquet",
                    "roles": ["data"],
                }
            },
        },
    )

    catalog = Catalog.open(tmp_path / "catalog.json")
    collections = list(catalog.collections())
    items = list(collections[0].items())
    collection_assets = list(collections[0].assets())
    item_assets = list(items[0].assets())

    assert catalog.id == "demo"
    assert [collection.id for collection in collections] == ["roads"]
    assert [item.id for item in items] == ["road-1"]
    assert collection_assets[0].href == (tmp_path / "roads" / "roads.parquet").as_uri()
    assert collection_assets[0].media_type == "application/vnd.apache.parquet"
    assert collection_assets[0].format is AssetFormat.GEOPARQUET
    assert collection_assets[0].roles == ("data",)
    assert item_assets[0].href == (tmp_path / "roads" / "road-1" / "road-1.parquet").as_uri()


def test_catalog_traverses_nested_child_catalogs(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "catalog.json",
        {
            "type": "Catalog",
            "stac_version": "1.1.0",
            "id": "root",
            "description": "Root catalog",
            "links": [
                {"rel": "child", "href": "./transport/catalog.json", "type": "application/json"}
            ],
        },
    )
    _write_json(
        tmp_path / "transport" / "catalog.json",
        {
            "type": "Catalog",
            "stac_version": "1.1.0",
            "id": "transport",
            "description": "Transport catalog",
            "links": [{"rel": "child", "href": "./roads/collection.json"}],
        },
    )
    _write_json(
        tmp_path / "transport" / "roads" / "collection.json",
        {
            "type": "Collection",
            "stac_version": "1.1.0",
            "id": "roads",
            "description": "Roads",
            "license": "CC-BY-4.0",
            "extent": {
                "spatial": {"bbox": [[-71.0, -35.0, -70.0, -34.0]]},
                "temporal": {"interval": [[None, None]]},
            },
            "links": [],
        },
    )

    catalog = Catalog.open(tmp_path)

    assert [collection.id for collection in catalog.collections()] == ["roads"]


def test_catalog_open_accepts_directory_path(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "catalog.json",
        {
            "type": "Catalog",
            "stac_version": "1.1.0",
            "id": "demo",
            "description": "Demo catalog",
            "links": [],
        },
    )

    catalog = Catalog.open(tmp_path)

    assert catalog.id == "demo"
    assert catalog.href == (tmp_path / "catalog.json").as_uri()


def test_asset_format_classification_uses_media_type_and_href() -> None:
    collection = {
        "type": "Collection",
        "id": "formats",
        "assets": {
            "parquet": {
                "href": "https://example.test/data",
                "type": "application/vnd.apache.parquet",
            },
            "cog": {"href": "https://example.test/image.tif"},
            "pmtiles": {
                "href": "https://example.test/tiles",
                "type": "application/vnd.pmtiles",
            },
            "unknown": {"href": "https://example.test/readme.txt", "type": "text/plain"},
        },
    }

    formats = {
        asset.key: asset.format
        for asset in Collection(collection, "https://example.test/collection.json").assets()
    }

    assert formats == {
        "parquet": AssetFormat.GEOPARQUET,
        "cog": AssetFormat.COG,
        "pmtiles": AssetFormat.PMTILES,
        "unknown": AssetFormat.UNKNOWN,
    }


def test_validator_reports_missing_required_catalog_fields(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "catalog.json",
        {
            "type": "Catalog",
            "id": "broken",
            "links": [{"href": "./roads/collection.json"}],
        },
    )

    result = Validator.validate(Catalog.open(tmp_path / "catalog.json"))

    assert not result.valid
    assert [(error.code, error.path) for error in result.errors] == [
        ("PTL-STAC-001", "catalog.stac_version"),
        ("PTL-STAC-001", "catalog.description"),
        ("PTL-STAC-002", "catalog.links[0].rel"),
    ]


def test_validator_reports_collection_item_and_asset_errors(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "catalog.json",
        {
            "type": "Catalog",
            "stac_version": "1.1.0",
            "id": "demo",
            "description": "Demo catalog",
            "links": [
                {"rel": "child", "href": "./roads/collection.json", "type": "application/json"}
            ],
        },
    )
    _write_json(
        tmp_path / "roads" / "collection.json",
        {
            "type": "Collection",
            "stac_version": "1.1.0",
            "id": "roads",
            "description": "Roads",
            "extent": {
                "spatial": {"bbox": [[-71.0, -35.0, -70.0, -34.0]]},
                "temporal": {"interval": [[None, None]]},
            },
            "links": [{"rel": "item", "href": "./road-1/road-1.json"}],
            "assets": {"data": {"type": "application/vnd.apache.parquet"}},
        },
    )
    _write_json(
        tmp_path / "roads" / "road-1" / "road-1.json",
        {
            "type": "Feature",
            "stac_version": "1.1.0",
            "id": "road-1",
            "properties": {"datetime": None},
            "links": [],
            "assets": {"data": {"href": "./road-1.parquet"}},
        },
    )

    result = Validator.validate(Catalog.open(tmp_path))

    assert not result.valid
    assert [(error.code, error.path) for error in result.errors] == [
        ("PTL-STAC-001", "collection.roads.license"),
        ("PTL-STAC-003", "collection.roads.assets.data.href"),
        ("PTL-STAC-001", "item.road-1.collection"),
    ]
