"""Catalog domain API tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from portolan import AssetFormat, Catalog, Collection, Item, Validator

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


def test_catalog_open_accepts_string_and_file_uri_sources(tmp_path: Path) -> None:
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

    from_string = Catalog.open(str(tmp_path / "catalog.json"))
    from_uri = Catalog.open((tmp_path / "catalog.json").as_uri())

    assert from_string.id == "demo"
    assert from_uri.id == "demo"


def test_catalog_rejects_non_object_json(tmp_path: Path) -> None:
    (tmp_path / "catalog.json").write_text("[]", encoding="utf-8")

    with pytest.raises(TypeError, match="Expected JSON object"):
        Catalog.open(tmp_path / "catalog.json")


def test_documents_ignore_invalid_links_and_assets() -> None:
    data = {
        "type": "Collection",
        "id": "roads",
        "links": [
            "not an object",
            {"rel": "self"},
            {"href": "./missing-rel.json"},
            {"rel": "item", "href": "./item.json", "type": "application/json", "title": "Item"},
        ],
        "assets": {
            "bad": "not an object",
            10: {"href": "./bad-key.parquet"},
            "missing_href": {"type": "application/vnd.apache.parquet"},
            "media_type": {
                "href": "./roads.parquet",
                "media_type": "application/vnd.apache.parquet",
                "roles": ["data", 5],
                "title": "Roads",
                "description": "Road network",
            },
        },
    }

    collection = Collection(data, "https://example.test/catalog/collection.json")
    links = list(collection.links())
    assets = list(collection.assets())

    assert [(link.rel, link.href, link.media_type, link.title) for link in links] == [
        (
            "item",
            "https://example.test/catalog/item.json",
            "application/json",
            "Item",
        )
    ]
    assert len(assets) == 1
    assert assets[0].key == "media_type"
    assert assets[0].media_type == "application/vnd.apache.parquet"
    assert assets[0].roles == ("data",)


def test_collection_items_only_yields_feature_documents(tmp_path: Path) -> None:
    _write_json(tmp_path / "asset.json", {"type": "Catalog", "id": "not-an-item", "links": []})
    _write_json(
        tmp_path / "item.json",
        {
            "type": "Feature",
            "stac_version": "1.1.0",
            "id": "road-1",
            "collection": "roads",
            "properties": {},
            "links": [],
        },
    )
    collection = Collection(
        {
            "type": "Collection",
            "id": "roads",
            "links": [
                {"rel": "root", "href": "./catalog.json"},
                {"rel": "item", "href": "./asset.json"},
                {"rel": "item", "href": "./item.json"},
            ],
        },
        (tmp_path / "collection.json").as_uri(),
    )

    assert [item.id for item in collection.items()] == ["road-1"]


def test_item_exposes_links_and_asset_metadata() -> None:
    item = Item(
        {
            "type": "Feature",
            "id": "road-1",
            "links": [{"rel": "self", "href": "./item.json"}],
            "assets": {
                "data": {
                    "href": "./data.pmtiles",
                    "title": "Tiles",
                    "description": "Vector tiles",
                }
            },
        },
        "https://example.test/items/road-1.json",
    )

    assert item.href == "https://example.test/items/road-1.json"
    assert item.data["id"] == "road-1"
    assert list(item.links())[0].href == "https://example.test/items/item.json"
    asset = list(item.assets())[0]
    assert asset.title == "Tiles"
    assert asset.description == "Vector tiles"
    assert asset.format is AssetFormat.PMTILES


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


def test_validator_reports_link_asset_extent_and_properties_shape_errors(
    tmp_path: Path,
) -> None:
    _write_json(
        tmp_path / "catalog.json",
        {
            "type": "Catalog",
            "stac_version": "1.1.0",
            "id": "demo",
            "description": "Demo catalog",
            "links": [{"rel": "child", "href": "./roads/collection.json"}],
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
            "extent": "not an object",
            "links": ["not an object", {"rel": "item", "href": "./road-1/road-1.json"}],
            "assets": ["not an object"],
        },
    )
    _write_json(
        tmp_path / "roads" / "road-1" / "road-1.json",
        {
            "type": "Feature",
            "stac_version": "1.1.0",
            "id": "road-1",
            "collection": "roads",
            "properties": [],
            "links": "not an array",
            "assets": {"bad": "not an object"},
        },
    )

    result = Validator.validate(Catalog.open(tmp_path))

    assert [(error.code, error.path) for error in result.errors] == [
        ("PTL-STAC-001", "collection.roads.extent"),
        ("PTL-STAC-002", "collection.roads.links[0]"),
        ("PTL-STAC-003", "collection.roads.assets"),
        ("PTL-STAC-001", "item.road-1.properties"),
        ("PTL-STAC-002", "item.road-1.links"),
        ("PTL-STAC-003", "item.road-1.assets.bad"),
    ]
