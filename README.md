# Portolan Python

A lightweight Python implementation of the Portolan specification.

`portolan-python` provides the core domain model, catalog access, validation, and conformance APIs required to work with Portolan catalogs from Python applications.

The project intentionally focuses on **Portolan itself**, rather than on geospatial data processing.

It does not aim to replace GDAL, Rasterio, GeoPandas, GeoParquet tooling, tile generators, GIS servers, or other specialized geospatial software.

## Motivation

Portolan defines an opinionated way of organizing and describing cloud-native geospatial data using existing standards and formats such as STAC, GeoParquet, COG, PMTiles, COPC, and Zarr.

Applications integrating with Portolan need a reliable implementation of that contract.

Without a reusable core library, every integration would need to independently implement:

* Portolan catalog semantics;
* STAC traversal;
* collection and asset handling;
* Portolan-specific requirements;
* link and HREF resolution;
* metadata validation;
* conformance rules;
* serialization and deserialization.

`portolan-python` provides that reusable implementation.

The core design principle is:

> **Portolan defines the contract. Specialized tools implement data processing.**

For example, this library may determine that an asset is a GeoParquet asset and expose its URI and metadata. It does not need to read the GeoParquet rows itself.

Likewise, it may identify a COG asset without becoming a raster processing library.

## Scope

`portolan-python` is responsible for the Portolan domain model and specification semantics.

Expected responsibilities include:

* opening Portolan catalogs;
* creating Portolan catalogs;
* reading and writing Portolan/STAC metadata;
* navigating catalogs, collections, items, assets, and links;
* resolving relative and absolute HREFs;
* exposing Portolan extensions and metadata;
* validating Portolan structures;
* checking Portolan conformance;
* exposing asset type and media-type information;
* handling specification versions;
* providing stable Python APIs for applications built on Portolan.

A conceptual API may look like:

```python
from portolan import Catalog

catalog = Catalog.open("https://example.com/catalog.json")

for collection in catalog.collections():
    print(collection.id)

    for asset in collection.assets():
        print(asset.href)
        print(asset.media_type)
        print(asset.roles)
```

Validation should similarly be available programmatically:

```python
from portolan import Catalog, Validator

catalog = Catalog.open("./catalog.json")

result = Validator.validate(catalog)

if not result.valid:
    for error in result.errors:
        print(error)
```

The exact API will evolve during implementation, but it should remain small, explicit, typed, and independent from any CLI.

## Non-goals

This project should **not** become a general-purpose geospatial processing library.

In particular, the core should not be responsible for:

* reading GeoParquet feature data;
* writing GeoParquet datasets;
* converting Shapefile to GeoParquet;
* creating COGs;
* reading raster pixels;
* creating PMTiles;
* processing COPC;
* converting MrSID or ECW;
* extracting data from WFS;
* extracting data from ArcGIS;
* extracting data from CARTO;
* publishing data to GeoServer;
* running pygeoapi;
* managing QGIS projects.

Those capabilities belong to specialized libraries, applications, or optional integrations.

Portolan should be opinionated about **what constitutes a conformant Portolan catalog and asset**, not unnecessarily opinionated about **which software must produce or consume those assets**.

## Architecture

```text
                    Portolan Specification
                             │
                             ▼
                      portolan-python
                   ┌────────────────────┐
                   │ Domain model       │
                   │ Catalog access     │
                   │ STAC semantics     │
                   │ Portolan semantics │
                   │ HREF resolution    │
                   │ Validation         │
                   │ Conformance        │
                   └─────────┬──────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
         portolan-cli   portolan-geoserver  other apps
```

## Relationship with `portolan-cli`

`portolan-cli` should consume this library rather than implement Portolan domain logic itself.

For example:

```text
portolan validate
portolan inspect
portolan registry list
```

should be CLI representations of APIs provided by the Portolan Python ecosystem.

The CLI should remain an interface layer.

## Relationship with `portolan-geoserver`

`portolan-geoserver` uses this library to understand Portolan catalogs and uses `python-geoservercloud` to interact with GeoServer.

The responsibilities remain separated:

```text
portolan-python
    │
    │ understands Portolan
    ▼
portolan-geoserver
    │
    │ maps Portolan resources to GeoServer
    ▼
python-geoservercloud
    │
    │ manages GeoServer
    ▼
GeoServer
```

`portolan-python` therefore contains no GeoServer-specific logic.

## Relationship with `portolan-java`

`portolan-java` is the Java counterpart of this project.

The two libraries should implement the same **conceptual Portolan contract**, while following the conventions of their respective languages.

They should not necessarily expose identical classes or method signatures.

The Portolan specification remains the source of truth.

```text
                 Portolan Specification
                    /             \
                   /               \
          portolan-python      portolan-java
```

## Design principles

1. Specification first.
2. Small and stable public API.
3. No CLI dependency.
4. No GIS server dependency.
5. No mandatory geospatial processing stack.
6. Specialized formats are represented, not reimplemented.
7. External applications should not need to reimplement Portolan semantics.
8. The library should be suitable as a dependency of long-lived applications.

---
