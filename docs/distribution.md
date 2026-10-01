# Distribution

Tagged releases provide immutable Python source and wheel archives. PyPI is the
preferred package index once its trusted publisher is configured.

## Release artifacts

Push a tag that matches the version in `pyproject.toml`:

```bash
git tag v0.1.0
git push origin v0.1.0
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
  https://github.com/jemacchi/portolan-python/releases/download/v0.1.0/portolan_python-0.1.0-py3-none-any.whl
```

This path needs no package index account.

## Publish to PyPI

The workflow supports PyPI trusted publishing. It uses a short-lived identity
token, so the repository does not store a permanent PyPI API token.

Complete these steps once:

1. Create the `portolan-python` project on PyPI, or add a pending publisher.
2. Add a trusted GitHub publisher for `jemacchi/portolan-python`.
3. Set the workflow name to `release.yml` and the environment to `pypi`.
4. Create the `pypi` environment in the GitHub repository.
5. Add the repository variable `PUBLISH_PYPI` with the value `true`.

After this setup, each valid version tag also publishes to PyPI. Consumers can
then use the normal command:

```bash
python -m pip install portolan-python==0.1.0
```

PyPI does not permit replacing a published version. Increase the version before
you publish another release.
