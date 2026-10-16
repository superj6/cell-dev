"""Run only the two unexecuted legacy fixtures; supply the required trial truth argument."""
import js_batch

js_batch.COMMANDS = [
    ('matching_trial64', ['test_delayed_match_trial64.js',
        str(js_batch.ROOT/'results/abi5_delayed_match_20261015/validation/truth_conservation_fix/truth.json')]),
    ('matching_view', ['test_delayed_match_view.js']),
]
# Keep the first command failure and all successful preceding tests unchanged.
js_batch.HERE = js_batch.HERE/'remaining'
js_batch.HERE.mkdir()
js_batch.HERE.joinpath('count_js_calls.cjs').write_text(
    js_batch.HERE.parent.joinpath('count_js_calls.cjs').read_text().replace(
        '../../../results/atlas/play/lifesim.js', '../../../../results/atlas/play/lifesim.js'))
raise SystemExit(js_batch.main())
