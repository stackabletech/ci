from subprocess import PIPE, TimeoutExpired, Popen
from time import sleep


def output_to_string_array(byte_stream):
    return [line.strip() for line in byte_stream.decode("utf-8").splitlines()]


def run_command(command, description, timeout=60, retries=1, delay=60):
    while retries > 0:
        exit_code, output = _run_command(command, description, timeout)
        if exit_code == 0:
            return exit_code, output
        retries = retries -1
        sleep(delay)
    return exit_code, output


def _run_command(command, description, timeout=60):
    """
        Execute command.
        Returns tuple (exit_code, output as multi-line)
    """
    proc = Popen(['/bin/bash', '-c', command], stdout=PIPE, stderr=PIPE)
    try:
        output, errs = proc.communicate(timeout=timeout)
    except TimeoutExpired:
        proc.kill()
        _, errs = proc.communicate()
        return -1, f"{description} timed out after {timeout} seconds."
    if proc.returncode != 0:
        return proc.returncode, output_to_string_array(errs)
    return 0, output_to_string_array(output)
