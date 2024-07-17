"""
    This module enables access to the catalog
"""

import hiyapyco

# variables holding the catalog data
providers = []
platforms = []
operator_tests = []

def read_providers(logger):
    """
        Reads the list of cluster providers from platforms.yaml

        logger              logger (String-consuming function)
    """
    global providers
    platforms_yaml = hiyapyco.load("/platforms.yaml")
    if not 'providers' in platforms_yaml:
        logger('platforms.yaml does not contain providers.')
        return False
    providers = platforms_yaml['providers']
    if len(providers) == 0:
        logger('platforms.yaml does not contain providers.')
        return False
    # TODO More syntax checks to make sure the catalog file is usable
    return True

def read_platforms(logger):
    """
        Reads the list of cluster platforms from platforms.yaml

        logger              logger (String-consuming function)
    """
    global platforms
    platforms = hiyapyco.load("/platforms.yaml")['platforms']
    platforms_yaml = hiyapyco.load("/platforms.yaml")
    if not 'platforms' in platforms_yaml:
        logger('platforms.yaml does not contain platforms.')
        return False
    platforms = platforms_yaml['platforms']
    if len(platforms) == 0:
        logger('platforms.yaml does not contain platforms.')
        return False
    # TODO More syntax checks to make sure the catalog file is usable
    return True

def read_operator_tests(logger):
    """
        Reads the list of operator test definitions from operator-tests.yaml

        logger              logger (String-consuming function)
    """
    global operator_tests
    operator_tests = hiyapyco.load("/operator-tests.yaml")
    if len(operator_tests) == 0:
        logger('operator-tests.yaml does not contain any tests.')
        return False
    # TODO More syntax checks to make sure the catalog file is usable
    return True

def read_catalog(logger):
    """
        Read all catalogs

        logger              logger (String-consuming function)
    """
    if not read_providers(logger):
        return False
    if not read_platforms(logger):
        return False
    if not read_operator_tests(logger):
        return False
    logger(f"Read {len(providers)} providers: [{','.join([p['id'] for p in providers])}]")
    logger(f"Read {len(platforms)} platforms: [{','.join([p['id'] for p in platforms])}]")
    logger(f"Read {len(operator_tests)} operator tests: [{','.join([ot['id'] for ot in operator_tests])}]")
    return True

def get_platform(platform):
    """
        Get the platform matching the platform string.
        If the platform string matches an ID, that platform is chosen.
        Otherwise, we search for a matching name attribute.

        platform        string which identifies a platform
    """
    matching_platform = next(filter(lambda p: p['id']==platform, platforms), None)
    if not matching_platform:
        matching_platform = next(filter(lambda p: p['name']==platform, platforms), None)
    return matching_platform

def get_spec_for_operator_test(operator_test, platform, logger):
    """
        Reads the cluster spec for the given operator/platform combination.

        The cluster spec is calculated combining up to 3 specs as following:

        1) Base spec: from platforms.yaml: 'spec' for the selected platform
        2) Test-specific spec: Overwrite fields which are specified in the 'spec' section of the given operator test.
        3) Platform-specific spec for operator test: Overwrite fields which are specified in the 'spec' section of the specific section for that platform inside the 'platforms' section of the operator test.

        operator_test:      ID of operator test
        platform            ID of platform

        Returns None and prints out an error message if the combination is not valid.
    """

    # Find the matching platform, exit if not existing
    matching_platform = next(filter(lambda p: p['id']==platform, platforms), None)
    if not matching_platform:
        logger(f"The platform '{platform}' does not exist.")
        return None

    # Find the matching operator test, exit if not existing
    matching_operator_test = next(filter(lambda ot: ot['id']==operator_test, operator_tests), None)
    if not matching_operator_test:
        logger(f"The operator test '{operator_test}' does not exist.")
        return None

    # Find out the matching definition for the given platform inside the given operator test, exit if not existing
    matching_operator_test_platform_def = next(filter(lambda p: p['id']==platform, matching_operator_test['platforms']), None)
    if not matching_operator_test_platform_def: 
        logger(f"The test for '{operator_test}' is not defined for the platform '{platform}'.")
        return None

    # The base spec from the platform
    spec = matching_platform['spec']

    # If there are more specific specs in the operator test, overwrite the specs with these.
    if 'spec' in matching_operator_test:
        spec = {**spec, **matching_operator_test['spec']}

    # If there are more specific specs in the operator test for the given platform, overwrite the specs with these.
    if 'spec' in matching_operator_test_platform_def:
        spec = {**spec, **matching_operator_test_platform_def['spec']}

    return spec