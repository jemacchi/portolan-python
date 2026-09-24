"""Domain model and catalog traversal for Portolan/STAC catalogs."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urljoin, urlparse
from urllib.request import Request, urlopen

JsonObject = dict[str, Any]


class AssetFormat(Enum):
    """Known cloud-native asset formats represented by Portolan catalogs."""

    GEOPARQUET = "GeoParquet"
    COG = "COG"
    PMTILES = "PMTiles"
    UNKNOWN = "Unknown"


@dataclass(frozen=True)
class Link:
    """A STAC link with its HREF resolved against the containing document."""

    rel: str
    href: str
    media_type: str | None
    title: str | None
    raw: JsonObject


@dataclass(frozen=True)
class Asset:
    """A STAC asset with Portolan-friendly accessors."""

    key: str
    href: str
    media_type: str | None
    roles: tuple[str, ...]
    title: str | None
    description: str | None
    raw: JsonObject

    @property
    def format(self) -> AssetFormat:
        """Return the known Portolan asset format, without reading the asset bytes."""
        media_type = self.media_type or ""
        href_path = urlparse(self.href).path.lower()
        if media_type == "application/vnd.apache.parquet" or href_path.endswith(".parquet"):
            return AssetFormat.GEOPARQUET
        if (
            media_type == "image/tiff; application=geotiff; profile=cloud-optimized"
            or href_path.endswith((".tif", ".tiff"))
        ):
            return AssetFormat.COG
        if media_type == "application/vnd.pmtiles" or href_path.endswith(".pmtiles"):
            return AssetFormat.PMTILES
        return AssetFormat.UNKNOWN


class Catalog:
    """A loaded Portolan catalog root."""

    def __init__(self, data: JsonObject, href: str) -> None:
        self._data = data
        self._href = href

    @classmethod
    def open(cls, source: str | Path) -> Catalog:
        """Open a local or remote Portolan catalog document."""
        href = _source_to_href(source)
        data = _read_json_href(href)
        return cls(data, href)

    @property
    def id(self) -> str:
        return str(self._data.get("id", ""))

    @property
    def href(self) -> str:
        return self._href

    @property
    def data(self) -> JsonObject:
        return dict(self._data)

    def links(self) -> Iterator[Link]:
        yield from _links(self._data, self._href)

    def collections(self) -> Iterator[Collection]:
        """Yield child collections, including collections below child catalogs."""
        yield from _collections_from_catalog(self._data, self._href, set())

    def item_links(self) -> Iterator[Link]:
        """Yield item links owned by this catalog subtree."""
        yield from _item_links_from_document(self._data, self._href, set())


class Collection:
    """A loaded STAC Collection within a Portolan catalog."""

    def __init__(self, data: JsonObject, href: str) -> None:
        self._data = data
        self._href = href

    @classmethod
    def open(cls, source: str | Path) -> Collection:
        """Open a local or remote STAC Collection document."""
        href = _source_to_href(source, default_document="collection.json")
        data = _read_json_href(href)
        return cls(data, href)

    @property
    def id(self) -> str:
        return str(self._data.get("id", ""))

    @property
    def href(self) -> str:
        return self._href

    @property
    def data(self) -> JsonObject:
        return dict(self._data)

    def links(self) -> Iterator[Link]:
        yield from _links(self._data, self._href)

    def assets(self) -> Iterator[Asset]:
        yield from _assets(self._data, self._href)

    def items(self) -> Iterator[Item]:
        """Yield linked items from this collection."""
        for link in self.item_links():
            data = _read_json_href(link.href)
            if data.get("type") == "Feature":
                yield Item(data, link.href)

    def item_links(self) -> Iterator[Link]:
        """Yield item links owned by this collection.

        A collection can group items behind child catalogs. Those items still
        belong to the collection, so traversal follows child catalogs and stops
        at child collections.
        """
        yield from _item_links_from_document(self._data, self._href, set())


class Item:
    """A loaded STAC Item."""

    def __init__(self, data: JsonObject, href: str) -> None:
        self._data = data
        self._href = href

    @classmethod
    def open(cls, source: str | Path) -> Item:
        """Open a local or remote STAC Item document."""
        href = _source_to_href(source, default_document="item.json")
        data = _read_json_href(href)
        return cls(data, href)

    @property
    def id(self) -> str:
        return str(self._data.get("id", ""))

    @property
    def href(self) -> str:
        return self._href

    @property
    def data(self) -> JsonObject:
        return dict(self._data)

    def links(self) -> Iterator[Link]:
        yield from _links(self._data, self._href)

    def assets(self) -> Iterator[Asset]:
        yield from _assets(self._data, self._href)


def _collections_from_catalog(
    data: JsonObject, href: str, visited: set[str]
) -> Iterator[Collection]:
    if href in visited:
        return
    visited.add(href)
    for link in _links(data, href):
        if link.rel != "child":
            continue
        child = _read_json_href(link.href)
        child_type = child.get("type")
        if child_type == "Collection":
            yield Collection(child, link.href)
        elif child_type == "Catalog":
            yield from _collections_from_catalog(child, link.href, visited)


def _item_links_from_document(data: JsonObject, href: str, visited: set[str]) -> Iterator[Link]:
    if href in visited:
        return
    visited.add(href)
    for link in _links(data, href):
        if link.rel == "item":
            yield link
        elif link.rel == "child":
            child = _read_json_href(link.href)
            if child.get("type") == "Catalog":
                yield from _item_links_from_document(child, link.href, visited)


def _links(data: JsonObject, document_href: str) -> Iterator[Link]:
    links = data.get("links")
    if not isinstance(links, list):
        return
    for raw_link in links:
        if not isinstance(raw_link, dict):
            continue
        rel = raw_link.get("rel")
        href = raw_link.get("href")
        if not isinstance(rel, str) or not isinstance(href, str):
            continue
        media_type = raw_link.get("type")
        title = raw_link.get("title")
        yield Link(
            rel=rel,
            href=_resolve_href(document_href, href),
            media_type=media_type if isinstance(media_type, str) else None,
            title=title if isinstance(title, str) else None,
            raw=dict(raw_link),
        )


def _assets(data: JsonObject, document_href: str) -> Iterator[Asset]:
    assets = data.get("assets")
    if not isinstance(assets, dict):
        return
    for key, raw_asset in assets.items():
        if not isinstance(key, str) or not isinstance(raw_asset, dict):
            continue
        href = raw_asset.get("href")
        if not isinstance(href, str):
            continue
        media_type = raw_asset.get("type") or raw_asset.get("media_type")
        roles = raw_asset.get("roles")
        title = raw_asset.get("title")
        description = raw_asset.get("description")
        yield Asset(
            key=key,
            href=_resolve_href(document_href, href),
            media_type=media_type if isinstance(media_type, str) else None,
            roles=tuple(role for role in roles if isinstance(role, str))
            if isinstance(roles, list)
            else (),
            title=title if isinstance(title, str) else None,
            description=description if isinstance(description, str) else None,
            raw=dict(raw_asset),
        )


def _source_to_href(source: str | Path, *, default_document: str = "catalog.json") -> str:
    if isinstance(source, Path):
        path = source
    else:
        parsed = urlparse(source)
        if parsed.scheme in {"http", "https", "file"}:
            return source
        path = Path(source)
    if path.is_dir():
        path = path / default_document
    return path.resolve().as_uri()


def _read_json_href(href: str) -> JsonObject:
    parsed = urlparse(href)
    if parsed.scheme in {"http", "https"}:
        request = Request(href, headers={"User-Agent": "portolan-python"})
        with urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    elif parsed.scheme == "file":
        path = Path(unquote(parsed.path))
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        data = json.loads(Path(href).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"Expected JSON object from {href}")
    return data


def _resolve_href(document_href: str, href: str) -> str:
    return urljoin(document_href, href)
