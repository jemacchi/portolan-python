# Examples

These examples use the public Python API. They do not invoke a CLI or read the
contents of geospatial assets.

## Install a released wheel

Until the package is published on PyPI, install a tagged release directly from
GitHub:

```bash
python -m pip install \
  https://github.com/jemacchi/portolan-python/releases/download/v0.1.4/portolan_python-0.1.4-py3-none-any.whl
```

You can also install the source at a specific tag:

```bash
python -m pip install \
  "portolan-python @ git+https://github.com/jemacchi/portolan-python.git@v0.1.4"
```

## List collections and assets

```python
from portolan import Catalog

catalog = Catalog.open("./catalog")

for collection in catalog.collections():
    print(collection.id)
    for asset in collection.assets():
        print(asset.key, asset.href, asset.media_type, asset.format.value)
```

`Catalog.open` accepts a directory, a JSON file path, a `file:` URI, or an
HTTP(S) URL.

## Validate a catalog

```python
from portolan import Catalog, Validator

catalog = Catalog.open("./catalog")
result = Validator.validate(catalog)

if not result.valid:
    for error in result.errors:
        print(error.code, error.path, error.message)
```

Validation returns structured errors. Callers decide whether to fail a build,
show a report, or continue with warnings.

## Build an asset inventory

This report answers a practical question: which formats occur in a catalog,
and where do they live?

```python
from collections import Counter

from portolan import Catalog

catalog = Catalog.open("https://example.com/catalog.json")
formats: Counter[str] = Counter()

for collection in catalog.collections():
    for asset in collection.assets():
        formats[asset.format.value] += 1
        print(f"{collection.id:24} {asset.format.value:12} {asset.href}")

print("\nInventory")
for format_name, count in formats.most_common():
    print(f"{format_name:12} {count:4}")
```

Format detection uses asset metadata and file extensions. It does not download
GeoParquet, COG, or PMTiles data.

## Read item links

```python
from portolan import Collection

collection = Collection.open("./catalog/roads")

for link in collection.item_links():
    print(link.raw["href"], "=>", link.href)
```

The raw HREF is the value written by the catalog. The resolved HREF is the value
an application can open.

## Use the registry API

```python
from pathlib import Path

from portolan import download_registry_catalog, load_registry_entries

entries = load_registry_entries(limit=5)

for entry in entries:
    print(entry.id, entry.url)

local_catalog = download_registry_catalog(entries[0].url, Path("./registry-cache"))
print(local_catalog)
```

The registry API reads the public registry export by default. Pass a registry
URL when you need a mirror or a test fixture.

## Find and validate one registry catalog

The registry can be used as an index. This example selects one entry, opens its
published catalog, and prints validation findings.

```python
from portolan import Catalog, Validator, load_registry_entries

matches = load_registry_entries(catalog_ids={"my-catalog"}, limit=1)
if not matches:
    raise SystemExit("Catalog not found")

catalog = Catalog.open(matches[0].url)
result = Validator.validate(catalog)

print(f"{catalog.id}: {'valid' if result.valid else 'invalid'}")
for error in result.errors:
    print(f"  {error.code} at {error.path}: {error.message}")
```

Replace `my-catalog` with an ID from the registry export.
