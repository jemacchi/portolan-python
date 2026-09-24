# Examples

These examples assume a local Portolan catalog at `./catalog`.

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
