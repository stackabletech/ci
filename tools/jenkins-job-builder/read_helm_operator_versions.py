from subprocess import PIPE, Popen

def read_helm_operator_versions():
    """
        Reads all available Stackable operator versions from our Helm repos
    """
    command = "helm search repo --versions --devel | grep stackable | grep '\\-operator' | awk -F'/' '{print $2}' | sort | awk '{print $1\"/\"$2}'"
    proc = Popen(['/bin/bash', '-c', command], stdout=PIPE, stderr=PIPE)
    output = proc.stdout.read()

    tuples = [tuple(l.decode('utf-8').split('/')) for l in output.splitlines()]

    keys = {t[0] for t in tuples}

    result = { key: [] for key in keys }

    for t in tuples:
        result[t[0]].append(t[1])

    for key in result:
        result[key].sort()

    return result