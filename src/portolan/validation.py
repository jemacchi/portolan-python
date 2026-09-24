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
        return ValidationResult(errors=tuple(errors))


def _validate_catalog_document(data: JsonObject, path: str, errors: list[ValidationError]) -> None:
    _require_string(data, "type", path, errors)
    _require_string(data, "stac_version", path, errors)
    _require_string(data, "id", path, errors)
    _require_string(data, "description", path, errors)
    _validate_links(data, path, errors)


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
