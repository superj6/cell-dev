import collections, functools, json, os, pathlib
counts = collections.Counter()
items = collections.Counter()
reports = collections.Counter()
def pytest_configure(config):
    from src.life import build, reference
    old_c, old_ref = build.run, reference._Life.run
    @functools.wraps(old_c)
    def c_run(worlds, seeds, **kwargs):
        node = os.environ.get('PYTEST_CURRENT_TEST', '').split('::', 1)[0]
        counts[(node, 'c_calls')] += 1
        counts[(node, 'c_lives')] += len(seeds)
        return old_c(worlds, seeds, **kwargs)
    @functools.wraps(old_ref)
    def ref_run(self):
        node = os.environ.get('PYTEST_CURRENT_TEST', '').split('::', 1)[0]
        counts[(node, 'reference_calls')] += 1
        counts[(node, 'reference_lives')] += 1
        return old_ref(self)
    build.run, reference._Life.run = c_run, ref_run
def pytest_collection_modifyitems(session, config, items):
    # pytest's hook signature uses items; retain a separate global counter.
    for item in items:
        globals()['items'][item.nodeid.split('::', 1)[0]] += 1
def pytest_runtest_logreport(report):
    if report.when == 'call' or report.failed:
        reports[(report.nodeid.split('::', 1)[0], report.outcome)] += 1
def pytest_sessionfinish(session, exitstatus):
    result = dict(exitstatus=int(exitstatus), collected=dict(items), reports={}, backend_calls={})
    for (path, key), value in reports.items():
        result['reports'].setdefault(path, {})[key] = value
    for (path, key), value in counts.items():
        result['backend_calls'].setdefault(path, {})[key] = value
    pathlib.Path(os.environ['ABI5_COUNTER_OUTPUT']).write_text(json.dumps(result, indent=2)+'\n')
