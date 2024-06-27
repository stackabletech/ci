# testing.stackable.tech

Configuration of our testing Jenkins (https://testing.stackable.tech)

## Catalog

This catalog contains the config data for the tests run in https://testing.stackable.tech.

* [platforms.yaml](catalog/platforms.yaml) contains the definition of the test system vendors and platforms
* [operator-tests.yaml](catalog/operator-tests.yaml) defines the integration tests for our operators

## Apps

Under [apps/](apps/), we maintain a bunch of Dockerized applications for the maintenance of Jenkins and to run the tests.

## Seed Job

The [seed job pipeline](jenkins/jobbuilder.groovy) to populate the Jenkins
