"""Small programmatic validation API for Portolan/STAC structures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from portolan.catalog import Catalog

JsonObject = dict[str, Any]


@dataclass(frozen=True)
class ValidationError:
    """One validation finding."""

    code: str
    path: str
    message: str


@dataclass(frozen=True)
class ValidationResult:
    """Validation outcome."""

    errors: tuple[ValidationError, ...]

    @property
    def valid(self) -> bool:
        return not self.errors


class Validator:
    """Validate loaded Portolan catalog structures."""

    @staticmethod
    def validate(catalog: Catalog) -> ValidationResult:
        """Validate a catalog and return structured findings."""
        errors: list[ValidationError] = []
        _validate_catalog_document(catalog.data, "catalog", errors)
        for collection in catalog.collections():
            collection_path = f"collection.{collection.id}"
            _validate_collection_document(collection.data, collection_path, errors)
            for item in collection.items():
                _validate_item_document(item.data, f"item.{item.id}", errors)
        return ValidationResult(errors=tuple(errors))


def _validate_catalog_document(data: JsonObject, path: str, errors: list[ValidationError]) -> None:
    _require_string(data, "type", path, errors)
    _require_string(data, "stac_version", path, errors)
    _require_string(data, "id", path, errors)
    _require_string(data, "description", path, errors)
    _validate_links(data, path, errors)


def _validate_collection_document(
    data: JsonObject, path: str, errors: list[ValidationError]
) -> None:
    _require_string(data, "type", path, errors)
    _require_string(data, "stac_version", path, errors)
    _require_string(data, "id", path, errors)
    _require_string(data, "description", path, errors)
    _require_string(data, "license", path, errors)
    if not isinstance(data.get("extent"), dict):
        errors.append(
            ValidationError(
                code="PTL-STAC-001",
                path=f"{path}.extent",
                message="extent is required",
            )
        )
    _validate_links(data, path, errors)
    _validate_assets(data, path, errors)


def _validate_item_document(data: JsonObject, path: str, errors: list[ValidationError]) -> None:
    _require_string(data, "type", path, errors)
    _require_string(data, "stac_version", path, errors)
    _require_string(data, "id", path, errors)
    _require_string(data, "collection", path, errors)
    if not isinstance(data.get("properties"), dict):
        errors.append(
            ValidationError(
                code="PTL-STAC-001",
                path=f"{path}.properties",
                message="properties is required",
            )
        )
    _validate_links(data, path, errors)
    _validate_assets(data, path, errors)


def _validate_assets(data: JsonObject, path: str, errors: list[ValidationError]) -> None:
    assets = data.get("assets")
    if assets is None:
        return
    if not isinstance(assets, dict):
        errors.append(
            ValidationError(
                code="PTL-STAC-003",
                path=f"{path}.assets",
                message="assets must be an object",
            )
        )
        return
    for key, asset in assets.items():
        asset_path = f"{path}.assets.{key}"
        if not isinstance(asset, dict):
            errors.append(
                ValidationError(
                    code="PTL-STAC-003",
                    path=asset_path,
                    message="asset must be an object",
                )
            )
            continue
        _require_string(asset, "href", asset_path, errors, code="PTL-STAC-003")


def _validate_links(data: JsonObject, path: str, errors: list[ValidationError]) -> None:
    links = data.get("links")
    if links is None:
        return
    if not isinstance(links, list):
        errors.append(
            ValidationError(
                code="PTL-STAC-002",
                path=f"{path}.links",
                message="links must be an array",
            )
        )
        return
    for index, link in enumerate(links):
        link_path = f"{path}.links[{index}]"
        if not isinstance(link, dict):
            errors.append(
                ValidationError(
                    code="PTL-STAC-002",
                    path=link_path,
                    message="link must be an object",
                )
            )
            continue
        _require_string(link, "rel", link_path, errors, code="PTL-STAC-002")
        _require_string(link, "href", link_path, errors, code="PTL-STAC-002")


def _require_string(
    data: JsonObject,
    field: str,
    path: str,
    errors: list[ValidationError],
    *,
    code: str = "PTL-STAC-001",
) -> None:
    value = data.get(field)
    if not isinstance(value, str) or not value:
        errors.append(
            ValidationError(
                code=code,
                path=f"{path}.{field}",
                message=f"{field} is required",
            )
        )
