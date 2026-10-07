# Distribution

Tagged releases provide immutable Python source and wheel archives. PyPI is the
preferred package index for published versions.

## Release artifacts

Push a tag that matches the version in `pyproject.toml`:

```bash
git tag v0.1.6
git push origin v0.1.6
```

The release workflow runs the tests, builds both distributions, checks their
metadata, and creates a GitHub release. It attaches the `.whl` and `.tar.gz`
files to that release.

The workflow rejects a tag that does not match the project version. Change the
version in `pyproject.toml` before the next release.

## Install from GitHub

Install the wheel attached to a release:

```bash
python -m pip install \
  https://github.com/jemacchi/portolan-python/releases/download/v0.1.6/portolan_python-0.1.6-py3-none-any.whl
```

This path needs no package index account.

## Install from PyPI

Install a published version from PyPI with:

```bash
python -m pip install portolan-python==0.1.6
```

Omit the version constraint to install the latest published version.
