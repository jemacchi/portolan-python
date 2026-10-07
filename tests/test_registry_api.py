"""Registry API tests."""

from __future__ import annotations

import json
from email.message import Message
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request

import pytest

from portolan import download_registry_catalog, load_registry_entries
from portolan.registry import _SameOriginRedirectHandler

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


def test_load_registry_entries_resolves_relative_child_urls() -> None:
    registry = {
        "links": [
            {
                "rel": "child",
                "href": "../demo/catalog.json",
                "portolan_registry:id": "demo",
                "portolan_registry:status": "valid",
            }
        ]
    }

    entries = load_registry_entries(
        "https://registry.test/exports/catalogs.json",
        fetch_json=lambda url: registry,
    )

    assert entries[0].url == "https://registry.test/demo/catalog.json"


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


def test_load_registry_entries_skips_invalid_link_shapes() -> None:
    registry = {
        "links": [
            "not an object",
            {"rel": "item", "href": "https://example.test/item.json"},
            {"rel": "child", "href": "https://example.test/missing-id/catalog.json"},
            {"rel": "child", "href": 5, "portolan_registry:id": "bad-href"},
            {
                "rel": "child",
                "href": "https://example.test/no-status/catalog.json",
                "title": 7,
                "portolan_registry:id": "no-status",
            },
        ]
    }

    hidden = load_registry_entries(
        "https://registry.test/catalogs.json",
        fetch_json=lambda url: registry,
    )
    included = load_registry_entries(
        "https://registry.test/catalogs.json",
        fetch_json=lambda url: registry,
        include_stale=True,
    )

    assert hidden == []
    assert [(entry.id, entry.title, entry.status) for entry in included] == [
        ("no-status", None, None)
    ]


def test_load_registry_entries_returns_empty_when_links_are_missing() -> None:
    assert (
        load_registry_entries("https://registry.test/catalogs.json", fetch_json=lambda url: {})
        == []
    )


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
    assert catalog["links"][0]["href"] == "roads/collection.json"
    assert collection["assets"]["data"]["href"] == "https://example.test/demo/roads/roads.parquet"


def test_download_registry_catalog_rewrites_downloaded_children_to_local_hrefs(
    tmp_path: Path,
) -> None:
    root_url = "https://example.test/demo/catalog.json"
    child_url = "https://example.test/demo/roads/collection.json"
    item_url = "https://example.test/demo/roads/item.json"
    responses = {
        root_url: {
            "type": "Catalog",
            "id": "demo",
            "links": [
                {"rel": "self", "href": root_url},
                {"rel": "child", "href": child_url},
                {"rel": "child", "href": item_url},
            ],
        },
        child_url: {
            **_collection("roads", {}),
            "links": [{"rel": "child", "href": root_url}],
        },
        item_url: {"type": "Feature", "id": "road-1"},
    }

    catalog_root = download_registry_catalog(
        root_url,
        tmp_path,
        fetch_json=lambda url: responses[url],
    )

    catalog = json.loads((catalog_root / "catalog.json").read_text(encoding="utf-8"))
    collection = json.loads(
        (catalog_root / "roads" / "collection.json").read_text(encoding="utf-8")
    )
    assert catalog["links"] == [
        {"rel": "self", "href": root_url},
        {"rel": "child", "href": "roads/collection.json"},
        {"rel": "child", "href": item_url},
    ]
    assert collection["links"] == [{"rel": "child", "href": "../catalog.json"}]


def test_download_registry_catalog_makes_non_downloaded_relative_links_absolute(
    tmp_path: Path,
) -> None:
    root_url = "https://example.test/demo/catalog.json"
    collection_url = "https://example.test/demo/roads/collection.json"
    feature_url = "https://example.test/demo/roads/features/road-1.json"
    responses = {
        root_url: {
            "type": "Catalog",
            "id": "demo",
            "links": [{"rel": "child", "href": "./roads/collection.json"}],
        },
        collection_url: {
            **_collection("roads", {}),
            "links": [
                {"rel": "item", "href": "./items/road-1.json"},
                {"rel": "child", "href": "./features/road-1.json"},
            ],
        },
        feature_url: {"type": "Feature", "id": "road-1"},
    }

    catalog_root = download_registry_catalog(
        root_url,
        tmp_path,
        fetch_json=lambda url: responses[url],
    )

    collection = json.loads(
        (catalog_root / "roads" / "collection.json").read_text(encoding="utf-8")
    )
    assert collection["links"] == [
        {"rel": "item", "href": "https://example.test/demo/roads/items/road-1.json"},
        {"rel": "child", "href": feature_url},
    ]


def test_download_registry_catalog_keeps_downloaded_root_and_parent_links_local(
    tmp_path: Path,
) -> None:
    root_url = "https://example.test/demo/catalog.json"
    collection_url = "https://example.test/demo/roads/collection.json"
    responses = {
        root_url: {
            "type": "Catalog",
            "id": "demo",
            "links": [{"rel": "child", "href": "./roads/collection.json"}],
        },
        collection_url: {
            **_collection("roads", {}),
            "links": [
                {"rel": "root", "href": root_url},
                {"rel": "parent", "href": root_url},
            ],
        },
    }

    catalog_root = download_registry_catalog(
        root_url,
        tmp_path,
        fetch_json=lambda url: responses[url],
    )

    collection = json.loads(
        (catalog_root / "roads" / "collection.json").read_text(encoding="utf-8")
    )
    assert collection["links"] == [
        {"rel": "root", "href": "../catalog.json"},
        {"rel": "parent", "href": "../catalog.json"},
    ]


def test_download_registry_catalog_skips_child_cycles(tmp_path: Path) -> None:
    root_url = "https://example.test/demo/catalog.json"
    child_url = "https://example.test/demo/roads/collection.json"
    responses = {
        root_url: {
            "type": "Catalog",
            "id": "demo",
            "links": [{"rel": "child", "href": "./roads/collection.json"}],
        },
        child_url: {
            **_collection("roads", {}),
            "links": [{"rel": "child", "href": "../catalog.json"}],
        },
    }
    fetched_urls: list[str] = []

    def fetch_json(url: str) -> dict[str, Any]:
        fetched_urls.append(url)
        if fetched_urls.count(url) > 1:
            raise AssertionError(f"Fetched document twice: {url}")
        return responses[url]

    download_registry_catalog(root_url, tmp_path, fetch_json=fetch_json)

    assert fetched_urls == [root_url, child_url]


@pytest.mark.parametrize(
    ("child_url", "message"),
    [
        ("https://other.test/demo/collection.json", "different origin"),
        ("https://example.test/demo/../../outside.json", "outside catalog root"),
    ],
)
def test_download_registry_catalog_rejects_unsafe_child_urls_before_fetch(
    child_url: str,
    message: str,
    tmp_path: Path,
) -> None:
    root_url = "https://example.test/demo/catalog.json"
    catalog = {
        "type": "Catalog",
        "id": "demo",
        "links": [{"rel": "child", "href": child_url}],
    }
    fetched_urls: list[str] = []

    def fetch_json(url: str) -> dict[str, Any]:
        fetched_urls.append(url)
        if url != root_url:
            raise AssertionError(f"Fetched unsafe child URL: {url}")
        return catalog

    with pytest.raises(ValueError, match=message):
        download_registry_catalog(root_url, tmp_path, fetch_json=fetch_json)

    assert fetched_urls == [root_url]


def test_download_registry_catalog_rejects_symlink_escape(tmp_path: Path) -> None:
    root_url = "https://example.test/demo/catalog.json"
    child_url = "https://example.test/demo/linked/collection.json"
    output_dir = tmp_path / "output"
    outside_dir = tmp_path / "outside"
    catalog_root = output_dir / "demo"
    outside_dir.mkdir()
    catalog_root.mkdir(parents=True)
    (catalog_root / "linked").symlink_to(outside_dir, target_is_directory=True)
    responses = {
        root_url: {
            "type": "Catalog",
            "id": "demo",
            "links": [{"rel": "child", "href": child_url}],
        },
        child_url: _collection("linked", {}),
    }

    download_registry_catalog(
        root_url,
        output_dir,
        fetch_json=lambda url: responses[url],
    )

    assert not (outside_dir / "collection.json").exists()
    assert (catalog_root / "linked" / "collection.json").exists()


def test_download_registry_catalog_rejects_catalog_root_symlink(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    outside_dir = tmp_path / "outside"
    output_dir.mkdir()
    outside_dir.mkdir()
    (output_dir / "demo").symlink_to(outside_dir, target_is_directory=True)

    with pytest.raises(ValueError, match="Catalog directory must not be a symlink"):
        download_registry_catalog(
            "https://example.test/demo/catalog.json",
            output_dir,
            fetch_json=lambda url: {"type": "Catalog", "id": "demo", "links": []},
        )

    assert list(outside_dir.iterdir()) == []


def test_download_registry_catalog_rejects_registry_id_mismatch(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="does not match registry id"):
        download_registry_catalog(
            "https://example.test/demo/catalog.json",
            tmp_path,
            expected_catalog_id="selected-catalog",
            fetch_json=lambda url: {"type": "Catalog", "id": "other-catalog", "links": []},
        )

    assert not (tmp_path / "selected-catalog").exists()


def test_download_registry_catalog_preserves_snapshot_when_child_fetch_fails(
    tmp_path: Path,
) -> None:
    catalog_root = tmp_path / "demo"
    catalog_root.mkdir()
    previous = catalog_root / "catalog.json"
    previous.write_text('{"id": "previous"}\n', encoding="utf-8")
    root_url = "https://example.test/demo/catalog.json"

    def fetch_json(url: str) -> dict[str, Any]:
        if url == root_url:
            return {
                "type": "Catalog",
                "id": "demo",
                "links": [{"rel": "child", "href": "./missing.json"}],
            }
        raise HTTPError(url, 503, "Unavailable", hdrs=Message(), fp=None)

    with pytest.raises(HTTPError):
        download_registry_catalog(root_url, tmp_path, fetch_json=fetch_json)

    assert previous.read_text(encoding="utf-8") == '{"id": "previous"}\n'
    assert not list(tmp_path.glob(".demo.staging-*"))


def test_same_origin_redirect_handler_rejects_cross_origin_redirect() -> None:
    handler = _SameOriginRedirectHandler("https://example.test/demo/catalog.json")

    with pytest.raises(HTTPError, match="Redirect changed origin"):
        handler.redirect_request(
            Request("https://example.test/demo/child.json"),
            fp=None,
            code=302,
            msg="Found",
            headers={},
            newurl="http://127.0.0.1/private",
        )


def test_download_registry_catalog_rejects_local_path_collisions(tmp_path: Path) -> None:
    root_url = "https://example.test/demo/catalog.json"
    first_url = "https://example.test/demo/collection.json?version=1"
    second_url = "https://example.test/demo/collection.json?version=2"
    responses = {
        root_url: {
            "type": "Catalog",
            "id": "demo",
            "links": [
                {"rel": "child", "href": first_url},
                {"rel": "child", "href": second_url},
            ],
        },
        first_url: _collection("first", {}),
        second_url: _collection("second", {}),
    }
    fetched_urls: list[str] = []

    def fetch_json(url: str) -> dict[str, Any]:
        fetched_urls.append(url)
        return responses[url]

    with pytest.raises(ValueError, match="same local path"):
        download_registry_catalog(root_url, tmp_path, fetch_json=fetch_json)

    assert fetched_urls == [root_url, first_url]


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


def test_download_registry_catalog_ignores_invalid_children_and_asset_shapes(
    tmp_path: Path,
) -> None:
    responses: dict[str, dict[str, Any]] = {
        "https://example.test/demo/catalog.json": {
            "type": "Catalog",
            "id": "demo",
            "links": [
                "not an object",
                {"rel": "child", "href": 100},
                {"rel": "child", "href": "./ignored/item.json"},
                {"rel": "child", "href": "./roads/collection.json"},
            ],
        },
        "https://example.test/demo/ignored/item.json": {
            "type": "Feature",
            "id": "ignored",
            "links": [],
        },
        "https://example.test/demo/roads/collection.json": {
            "type": "Collection",
            "id": "roads",
            "links": [],
            "assets": {
                "bad": "not an object",
                "missing_href": {"type": "application/vnd.apache.parquet"},
                "data": {"href": "./roads.parquet"},
            },
        },
    }

    catalog_root = download_registry_catalog(
        "https://example.test/demo/catalog.json",
        tmp_path,
        fetch_json=lambda url: responses[url],
    )

    collection = json.loads(
        (catalog_root / "roads" / "collection.json").read_text(encoding="utf-8")
    )
    assert not (catalog_root / "ignored" / "item.json").exists()
    assert collection["assets"]["bad"] == "not an object"
    assert collection["assets"]["missing_href"] == {"type": "application/vnd.apache.parquet"}
    assert collection["assets"]["data"]["href"] == "https://example.test/demo/roads/roads.parquet"


def test_download_registry_catalog_handles_collections_without_asset_objects(
    tmp_path: Path,
) -> None:
    responses: dict[str, dict[str, Any]] = {
        "https://example.test/demo/catalog.json": {
            "type": "Catalog",
            "id": "demo",
            "links": [{"rel": "child", "href": "./roads/collection.json"}],
        },
        "https://example.test/demo/roads/collection.json": {
            "type": "Collection",
            "id": "roads",
            "links": [],
            "assets": [],
        },
    }

    catalog_root = download_registry_catalog(
        "https://example.test/demo/catalog.json",
        tmp_path,
        fetch_json=lambda url: responses[url],
    )

    collection = json.loads(
        (catalog_root / "roads" / "collection.json").read_text(encoding="utf-8")
    )
    assert collection["assets"] == []


def test_download_registry_catalog_rejects_id_outside_output_directory(tmp_path: Path) -> None:
    catalog = {"type": "Catalog", "id": "../../outside", "links": []}

    with pytest.raises(ValueError, match="safe directory name"):
        download_registry_catalog(
            "https://example.test/demo/catalog.json",
            tmp_path,
            fetch_json=lambda url: catalog,
        )


def test_download_registry_catalog_rejects_non_http_url(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must use HTTP or HTTPS"):
        download_registry_catalog("file:///tmp/catalog.json", tmp_path)
