"""Copy exact frozen AG terminal evidence; never edit released source files."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[2]
A=Path(__file__).resolve().parent
S=ROOT/'outputs/autonomous_visibility_dark_tail_gradient_20261014'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
names=['review_terminal.py','build_terminal_verifier.py','terminal_verifier_preparation.json','independent_terminal_raw_review.json','terminal_execution_review.json','terminal_raw_review.stdout.json','terminal_raw_review.stderr.txt','frozen_reanalysis.stdout.json','frozen_reanalysis.stderr.txt','frozen_reader_reanalysis/summary.json','frozen_reader_reanalysis/paired_vectors.npz','release_prerequisites.json','release_console.json','preparation_index_verification.json','preparation_commit.log','clearance_console.json','analysis_console.json','analysis_stderr.txt','monitor_console.log','terminal_text.md','update_terminal_docs.py','all_archive_files.txt','force_add_paths.txt']
pins={'independent_terminal_raw_review.json':'a5d507395ff1eb14c496ecf8d63b151c69353037db459db6080cdc33a9e3f7ab','terminal_execution_review.json':'06650d3a7ed4bdff14db833f0c2df8c9dde4e6159896c8b2f86af7288b6768fb','figures/generate.py':'9233e2ad51f33be629ca0304fb3215d00f23ac37471e8d4f9631fe863328c7a7','figures/capture_and_economy.png':'a91aa1ef9c514f4ec41defa437581368b383fd7049c3e4933f2294ee340ede8c','figures/capture_and_economy.svg':'c76b411e4f0d45bf36a922faa9e738f7d6a7a962ca9afdf7d87c353af316d9e3'}
for n,h in pins.items():assert sha(A/n)==h,n
sources=[(A/n,S/'terminal_review'/n) for n in names]
sources += [(A/'figures'/n,S/'figures'/n) for n in ('generate.py','capture_and_economy.png','capture_and_economy.svg')]
sources.append((Path(__file__),S/'terminal_review/copy_terminal_review.py'))
copied={}
for src,dst in sources:
 data=src.read_bytes()
 if dst.exists():assert dst.read_bytes()==data,dst
 else:dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(data)
 copied[str(dst.relative_to(S))]={'sha256':sha(dst),'source':str(src.relative_to(ROOT))}
r={'status':'exact_terminal_copies','files':copied,'simulation_calls':0,'compiled_libraries':0,'frozen_files_modified':False}
(A/'terminal_copy_receipt.json').write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps({'copied':len(copied),'receipt_sha256':sha(A/'terminal_copy_receipt.json')}))
