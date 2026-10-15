"""Curated byte-exact prospective review copies; no fixture trees or scientific execution."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
STUDY=ROOT/'outputs/autonomous_prediction_continuation_20261014'
NAMES=('source_preparation_review.json','source_origins.json','cost_feasibility.json','source_tests.log','source_tests.xml',
 'independent_source_design_review.json','review_source_design.py','source_design_stdout.json','source_design_stderr.txt',
 'history/source_review_initial_helper_error.txt','actual_preparation_review.json','preparation_command.json',
 'preparation_stdout.json','preparation_stderr.txt','check_actual_preparation.py','independent_actual_preparation_review.json',
 'actual_review_stdout.json','actual_review_stderr.txt','register_study.py','registration_console.json',
 'registration_prerequisites.json','preregister_text.md','update_preregister_docs.py','release_study.py','clear_terminal.py',
 'watchable_ui_scientific_review.json','watchable_document_history.json','archive.py','prepare_archive_sources.py',
 'copy_release_review.py','ARCHIVE.md','NAMESPACE_PROVENANCE.md')
for name in NAMES:
 p=OUT/name;q=STUDY/'release_review'/name
 raw=p.read_bytes();q.parent.mkdir(parents=True,exist_ok=True)
 if q.exists() and q.read_bytes()!=raw:raise ValueError('curated frozen review differs: '+name)
 if not q.exists():q.write_bytes(raw)
assert all((STUDY/'release_review'/n).read_bytes()==(OUT/n).read_bytes() for n in NAMES)
print(json.dumps({'copied_curated_files':len(NAMES),'source_pins':{n:hashlib.sha256((OUT/n).read_bytes()).hexdigest() for n in NAMES},'simulation_calls':0,'compiled_libraries':0},indent=2))
