# Development

The project uses `uv` for dependency management and build isolation.

## Setup

```bash
make setup
```

This installs runtime and development dependencies from `pyproject.toml`.

## Test and check

```bash
make test
make lint
make typecheck
make check
```

`make check` runs lint, type checking, and the test suite. The test command also
enforces the configured coverage floor.

## Build

```bash
make build
```

The build target creates source and wheel distributions in `dist/`.

## Clean local artifacts

```bash
make clean
```

This removes local build, cache, and coverage directories. It does not remove
source files or the virtual environment.
