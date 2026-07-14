# testing.stackable.tech

Configuration of our testing Jenkins (https://testing.stackable.tech)

## Catalog

This catalog contains the config data for the tests run in https://testing.stackable.tech.

* [platforms.yaml](catalog/platforms.yaml) contains the definition of the test system vendors and platforms
* [operator-tests.yaml](catalog/operator-tests.yaml) defines the integration tests for our operators

See this [Nuclino page](https://app.nuclino.com/Stackable/Engineering/Configuring-Test-Jobs-4e993d84-19b4-4081-846d-738f9f38573d) for further information.

### Updating the catalog

[`scripts/update-platforms.py`](scripts/update-platforms.py) refreshes the Kubernetes
versions in `platforms.yaml`. It fetches the latest versions from the Replicated and
IONOS APIs, keeps the latest patch per minor version line, adds ARM variants where
supported, and rewrites the file.

The script owns the layout of `platforms.yaml` completely, so **do not hand-edit that
file** — re-run the script instead. Re-running it on an unchanged catalog produces no
diff, so any diff you see is a real version change.

Prerequisites:

* Python 3 with `PyYAML` (`pip install pyyaml`)
* [`replicated`](https://docs.replicated.com/reference/replicated-cli-installing) CLI,
  authenticated (`REPLICATED_API_TOKEN`)
* [`ionosctl`](https://github.com/ionos-cloud/ionosctl) CLI, authenticated

Run it from the repository root and review the diff before committing:

```bash
python3 scripts/update-platforms.py
git diff catalog/platforms.yaml
```

[`scripts/check-catalog.py`](scripts/check-catalog.py) validates that `platforms.yaml`
and `operator-tests.yaml` are consistent (every platform referenced by a test exists,
every platform has a known provider). It exits non-zero on errors, so it is suitable
for CI. Run it after editing either catalog file:

```bash
python3 scripts/check-catalog.py
```

## Apps

Under [apps/](apps/README.md), we maintain a bunch of Dockerized applications for the maintenance of Jenkins and to run the tests.

## Seed Job

The [seed job pipeline](jenkins/jobbuilder.groovy) to populate the Jenkins

## Tools

The [tools folder](tools/) contains Dockerized tools to be run in the maintenance jobs. They are not strictly related to testing, but found their home here because this is the only Jenkins we have.
