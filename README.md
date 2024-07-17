# testing.stackable.tech

Configuration of our testing Jenkins (https://testing.stackable.tech)

## Catalog

This catalog contains the config data for the tests run in https://testing.stackable.tech.

* [platforms.yaml](catalog/platforms.yaml) contains the definition of the test system vendors and platforms
* [operator-tests.yaml](catalog/operator-tests.yaml) defines the integration tests for our operators

See this [Nuclino page](https://app.nuclino.com/Stackable/Engineering/Configuring-Test-Jobs-4e993d84-19b4-4081-846d-738f9f38573d) for further information.

## Apps

Under [apps/](apps/README.md), we maintain a bunch of Dockerized applications for the maintenance of Jenkins and to run the tests.

## Seed Job

The [seed job pipeline](jenkins/jobbuilder.groovy) to populate the Jenkins

## Tools

The [tools folder](tools/) contains Dockerized tools to be run in the maintenance jobs. They are not strictly related to testing, but found their home here because this is the only Jenkins we have.
