"""Publish reviewed AI viewer artifacts; execute no simulation or browser."""
from pathlib import Path
import hashlib
import json
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PUBLIC = ROOT / 'results/ai_watchable_20261014'
HTML = ROOT / 'results/atlas/exploratory_reserve_replication.html'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert not PUBLIC.exists() and not HTML.exists()
    review = json.loads((HERE / 'root_review.json').read_text())
    assert review['status'] == 'passed_data_and_layout_review_with_browser_exit_limitation'
    candidate = json.loads((HERE / 'publication_candidate_review.json').read_text())
    original = (HERE / 'exploratory_reserve_replication.html').read_text()
    html = (HERE / 'publication_candidate.html').read_text()
    assert sha(HERE / 'publication_candidate.html') == candidate['candidate_html_sha256']
    assert sha(HERE / 'exploratory_reserve_replication.html') == candidate['original_html_sha256']
    assert original.count(candidate['footer_before']) == 1
    assert original.replace(candidate['footer_before'], candidate['footer_after']) == html
    for link in re.findall(r'href="([^"]+)"', html):
        assert not link.startswith(('http:', 'https:', '//'))
        assert (HTML.parent / link).resolve().is_file(), link
    assert '</script><script>' in html
    PUBLIC.mkdir()
    mapping = {}
    for path in sorted(HERE.rglob('*')):
        if not path.is_file():
            continue
        rel = path.relative_to(HERE)
        if any(part in ('profile', 'cache', '__pycache__') for part in rel.parts):
            continue
        target = PUBLIC / ('historical_source_only_README.md' if str(rel) == 'README.md' else rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
        mapping[str(target.relative_to(PUBLIC))] = str(path.relative_to(ROOT))
    (PUBLIC / 'README.md').write_bytes((HERE / 'PUBLIC_README.md').read_bytes())
    mapping['README.md'] = str((HERE / 'PUBLIC_README.md').relative_to(ROOT))
    HTML.write_bytes((HERE / 'publication_candidate.html').read_bytes())
    artifacts = {}
    for path in sorted(PUBLIC.rglob('*')):
        if path.is_file():
            key = str(path.relative_to(PUBLIC))
            artifacts[key] = {'sha256': sha(path), 'bytes': path.stat().st_size, 'source': mapping[key]}
    manifest = {'status': 'published_viewer_with_explicit_browser_exit_limitation', 'artifacts': artifacts,
                'external_artifacts': {str(HTML.relative_to(ROOT)): {'sha256': sha(HTML), 'bytes': HTML.stat().st_size}},
                'root_review_sha256': sha(HERE / 'root_review.json'),
                'new_research_lives': 0, 'engineering_JS_replay_lives': 3,
                'paused_browser_initializations': 3, 'paused_browser_completed_lives': 0,
                'excluded_runtime_directories': ['paused_browser/profile', 'paused_browser/cache']}
    (PUBLIC / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'artifacts': len(artifacts), 'manifest_sha256': sha(PUBLIC / 'manifest.json'),
                      'html_sha256': sha(HTML), 'new_lives': 0}))


if __name__ == '__main__':
    main()
