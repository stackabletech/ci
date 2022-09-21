import os
import json
import re

PRODUCTS = ['airflow', 'druid', 'hbase', 'hdfs', 'hive', 'kafka', 'nifi', 'opa', 'spark-k8s', 'superset', 'trino', 'zookeeper']
REGEX_RESULT_FROM_LOG = re.compile('^Finished: ([A-Z]*)')
REGEX_DATE_TIME = re.compile('^(((\d{4}-\d\d-\d\d) \d\d:\d\d:\d\d)\.\d*)')
REGEX_PARALLELISM = re.compile('.*--parallel (\d+)\).*')
REGEX_TESTCASE_SUMMARY = re.compile('.*--- ([A-Z]+): kuttl/harness/(.+) \((\d+)\.\d+s\)\s*')
REGEX_TEST_STEP_HEADER_LINE = re.compile('.*=== CONT  kuttl/harness/(.+)\s*')
REGEX_TEST_STEP_START = re.compile('.*\s*(\d\d:\d\d:\d\d)\s*.*starting test step (\S+)\s*')
REGEX_TEST_STEP_END = re.compile('.*\s*(\d\d:\d\d:\d\d)\s*.*test step\s+([a-z]+)\s+(\S+)\s*')
REGEX_TEST_STEP_END_ALTERNATIVE_FAIL = re.compile('.*\s*failed in step\s+(\S+)\s*')
REGEX_TIME = re.compile('(\d\d):(\d\d):(\d\d)')

def analyze_test_output_file(test_output_file_name):
    if os.path.isfile(test_output_file_name):
        with open (test_output_file_name, 'r') as f:
            print(f.readline())

def analyze_product(product):
    print(f"Analyzing build jobs for '{product}'...")
    subfolders = [ f.path for f in os.scandir(f"/var/jenkins_home/jobs/{product}-operator-it-nightly/builds/") if f.is_dir() ]
    subfolders.sort()
    for subfolder in subfolders:
        analyze_test_output_file(f"{subfolder}/archive/testsuite/target/testdriver.log")


def get_build_result(folder):
    console_log_file = f"{folder.path}/log"
    if not os.path.isfile(console_log_file):
        return None
    with open(console_log_file) as f:
        for line in f:
            pass
        last_line = line
    matcher = REGEX_RESULT_FROM_LOG.match(last_line)
    if matcher:
        return matcher.group(1)
    return None


def get_date_time(folder):
    testdriver_log_file = f"{folder.path}/archive/testsuite/target/testdriver.log"
    if not os.path.isfile(testdriver_log_file):
        return None
    with open(testdriver_log_file) as f:
        first_line = f.readline()
    matcher_date = REGEX_DATE_TIME.match(first_line)
    if matcher_date:
        return matcher_date.groups()
    return None


def get_parallelism(folder):
    testdriver_log_file = f"{folder.path}/archive/testsuite/target/testdriver.log"
    if not os.path.isfile(testdriver_log_file):
        return 0
    with open(testdriver_log_file) as f:
        for line in f:
            matcher_parallelism = REGEX_PARALLELISM.match(line)
            if matcher_parallelism:
                return int(matcher_parallelism.group(1))
    return 0


def build(product, folder):
    build_result = get_build_result(folder)
    if not build_result:
        return None
    date_time = get_date_time(folder)
    if not date_time:
        return None
    parallelism = get_parallelism(folder)
    return { 
            'product': product, 
            'build': folder.name, 
            'jenkins_path': folder.path, 
            'result': build_result, 
            'date': date_time[2],
            'date_time': date_time[1],
            'timestamp': date_time[0],
            'parallel' : parallelism
        }


def builds(product):
    subfolders = [ f for f in os.scandir(f"/var/jenkins_home/jobs/{product}-operator-it-nightly/builds/") if f.is_dir() ]
    return list(filter(None, [ build(product, s) for s in subfolders]))


def archive(filename, content):
    with open (f"target/{filename}", "w") as f:
        f.write(json.dumps(content, indent=2))
        f.close()

def testcases(build):
    testcases = []
    test_output_file = f"{build['jenkins_path']}/archive/testsuite/target/test-output.log"
    if not os.path.isfile(test_output_file):
        test_output_file = f"{build['jenkins_path']}/archive/testsuite/target/test_output.log"
        if not os.path.isfile(test_output_file):
            return testcases
    with open(test_output_file) as f:
        for line in f:
            matcher_testcase = REGEX_TESTCASE_SUMMARY.match(line)
            if matcher_testcase:
                testcases.append({
                    'product': build['product'], 
                    'build': build['build'],
                    'date': build['date'], 
                    'date_time': build['date_time'], 
                    'parallel': build['parallel'], 
                    'testcase': matcher_testcase.group(2),
                    'result': 'passed' if matcher_testcase.group(1) == 'PASS' else 'failed',
                    'duration_sec': int(matcher_testcase.group(3))
                })
    return testcases


def teststep_duration(teststep):
    if not 'start_time' in teststep:
        return 0
    if not 'end_time' in teststep:
        return 0
    matcher_start_time = REGEX_TIME.match(teststep['start_time'])
    matcher_end_time = REGEX_TIME.match(teststep['end_time'])
    if not matcher_start_time or not matcher_end_time:
        return 0
    seconds_start_time = int(matcher_start_time.group(1))*3600 + int(matcher_start_time.group(2))*60 + int(matcher_start_time.group(3))
    seconds_end_time = int(matcher_end_time.group(1))*3600 + int(matcher_end_time.group(2))*60 + int(matcher_end_time.group(3))
    return (seconds_end_time - seconds_start_time + 86400) % 86400


def teststeps(build):
    teststeps_grouped_by_testcase = {}
    test_output_file = f"{build['jenkins_path']}/archive/testsuite/target/test-output.log"
    if not os.path.isfile(test_output_file):
        test_output_file = f"{build['jenkins_path']}/archive/testsuite/target/test_output.log"
        if not os.path.isfile(test_output_file):
            return []
    with open(test_output_file) as f:
        current_testcase = None
        for line in f:
            matcher_testcase = REGEX_TEST_STEP_HEADER_LINE.match(line)
            matcher_teststep_start = REGEX_TEST_STEP_START.match(line)
            matcher_teststep_end = REGEX_TEST_STEP_END.match(line)
            matcher_teststep_failed_alternative_text = REGEX_TEST_STEP_END_ALTERNATIVE_FAIL.match(line)
            if matcher_testcase:
                current_testcase = matcher_testcase.group(1)
                if not current_testcase in teststeps_grouped_by_testcase:
                    teststeps_grouped_by_testcase[current_testcase] = {}
            elif matcher_teststep_start:
                test_step_start_time = matcher_teststep_start.group(1)
                test_step_name = matcher_teststep_start.group(2)
                if not current_testcase:
                    print(f"Error in {test_output_file}: test step {test_step_name} started outside of test case context.")
                    return []
                if not test_step_name in teststeps_grouped_by_testcase[current_testcase]:
                    teststeps_grouped_by_testcase[current_testcase][test_step_name] = {}
                if 'start_time' in teststeps_grouped_by_testcase[current_testcase][test_step_name]:
                    print(f"Error in {test_output_file}: test step {test_step_name} started twice?")
                    return []
                teststeps_grouped_by_testcase[current_testcase][test_step_name]['start_time'] = test_step_start_time
            elif matcher_teststep_end:
                test_step_end_time = matcher_teststep_end.group(1)
                test_step_name = matcher_teststep_end.group(3)
                test_step_result = matcher_teststep_end.group(2)
                if not current_testcase:
                    print(f"Error in {test_output_file}: test step {test_step_name} ended outside of test case context.")
                    return []
                if not test_step_name in teststeps_grouped_by_testcase[current_testcase]:
                    print(f"Error in {test_output_file}: test step {test_step_name} ended before being started.")
                    return []
                if 'end_time' in teststeps_grouped_by_testcase[current_testcase][test_step_name]:
                    print(f"Error in {test_output_file}: test step {test_step_name} ended twice?")
                    return []
                teststeps_grouped_by_testcase[current_testcase][test_step_name]['end_time'] = test_step_end_time
                teststeps_grouped_by_testcase[current_testcase][test_step_name]['result'] = test_step_result
            elif matcher_teststep_failed_alternative_text:
                test_step_name = matcher_teststep_failed_alternative_text.group(1)
                if not current_testcase:
                    print(f"Error in {test_output_file}: test step {test_step_name} ended outside of test case context.")
                    return []
                if not test_step_name in teststeps_grouped_by_testcase[current_testcase]:
                    print(f"Error in {test_output_file}: test step {test_step_name} ended before being started.")
                    return []
                teststeps_grouped_by_testcase[current_testcase][test_step_name]['result'] = 'failed'

    return [ 
        {  
            'product': build['product'], 
            'build': build['build'],
            'date': build['date'], 
            'date_time': build['date_time'], 
            'parallel': build['parallel'], 
            'testcase': testcase,
            'teststep': teststep,
            'result': 'passed' if teststeps_grouped_by_testcase[testcase][teststep]['result'] == 'completed' else teststeps_grouped_by_testcase[testcase][teststep]['result'],
            'duration_sec': teststep_duration(teststeps_grouped_by_testcase[testcase][teststep])
        } for testcase in teststeps_grouped_by_testcase for teststep in teststeps_grouped_by_testcase[testcase]]


def duration_series(testcases):
    return [ { 'duration_sec': tc['duration_sec'], 'result': tc['result'] } for tc in testcases ]


def is_flaky_series(runs):
    allPassed = all((lambda run: run['result']=='passed')(run) for run in runs)
    allFailed = all((lambda run: run['result']=='failed')(run) for run in runs)
    return not (allPassed or allFailed)

def add_average_failure_duration_ratio(testcase):
    fails_durations = [ run['duration_sec'] for run in testcase['runs'] if run['result'] == 'failed']
    pass_durations = [ run['duration_sec'] for run in testcase['runs'] if run['result'] == 'passed']

    testcase['average_failure_duration_ratio'] = (sum(fails_durations)/len(fails_durations))  / (sum(pass_durations)/len(pass_durations))

if __name__ == "__main__":

    archive('products.json', PRODUCTS)
    print(f"Dumped {len(PRODUCTS)} products.")

    builds_grouped_by_product = [ builds(p) for p in PRODUCTS ]
    builds_flat = sorted([ b for g in builds_grouped_by_product for b in g ], key=lambda b: (b['product'], b['timestamp']))
    archive('builds.json', builds_flat)
    print(f"Dumped {len(builds_flat)} builds.")

    testcases_grouped_by_build = [ testcases(b) for b in builds_flat ]
    testcases_flat = sorted([t for g in testcases_grouped_by_build for t in g], key=lambda b: (b['product'], b['date'], b['testcase']))
    archive('testcases.json', testcases_flat)
    print(f"Dumped {len(testcases_flat)} test cases.")

    teststeps_grouped_by_build = [teststeps(b) for b in builds_flat ]
    teststeps_flat = sorted([t for g in teststeps_grouped_by_build for t in g], key=lambda b: (b['product'], b['date'], b['testcase'], b['teststep']))
    archive('teststeps.json', teststeps_flat)
    print(f"Dumped {len(teststeps_flat)} test steps.")

    test_runs_grouped_by_testcase = {}
    for tc in testcases_flat:
        test_runs_grouped_by_testcase.setdefault(f"{tc['product']}/{tc['testcase']}", []).append(tc)
 
    test_case_duration_series = [ { 'name': tc, 'runs': duration_series(test_runs_grouped_by_testcase[tc]) } for tc in test_runs_grouped_by_testcase ]
    test_case_duration_series = [ tc for tc in test_case_duration_series if is_flaky_series(tc['runs']) ]
    for tc in test_case_duration_series:
        add_average_failure_duration_ratio(tc)
    test_case_duration_series = sorted(test_case_duration_series, key=lambda tc: tc['average_failure_duration_ratio'])        

    with open (f"target/timeout-flakiness.txt", "w") as f:
        for tc in test_case_duration_series:
            f.write(f"{tc['name']}\n")
            f.write(f"ratio [average failure duration/average pass duration]: {tc['average_failure_duration_ratio']}\n")
            for run in tc['runs']:
                f.write(f"{run['result']} after {run['duration_sec']} sec\n")
            f.write("\n")
        f.close()

