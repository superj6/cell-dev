# Interactive population explorer

Open [population_explorer.html](population_explorer.html) directly in a browser. No server, installation or
network connection is needed. Hover or focus a point to highlight the same genome in every scatterplot; click
to keep it selected. The menu reaches overlapping points, and Clear selection or Escape resets the view.
The detail panel shows all five task means ± SE, original row/native ID, historical endpoint status and fresh
descriptive rank. Selected points display ±1 SE bars.

All 97 fixed genomes and all saved means are retained from the completed public population diagnostic.
The page explains the 32-life development uncertainty, shared seeds and lack of winner certification or
endpoint replacement. Friendly task/population labels supplement the original IDs. The AO star, reference
lines and historical reporting outlines reproduce the meaning of the published static scatterplot.

`render.py` uses only Python's standard library and the SHA-pinned completed CSV, summary, row manifest and
completion/table receipts. `client.js` and `template.html` are embedded in the 156 kB HTML. Rendering checked
all 485 CSV rows and 3,880 numeric means/SE against the summary, plus row identities, endpoint flags and
embedded bytes. Ruff, AST and Node syntax checks passed. No simulator, build or random draw was invoked;
no real browser was tested. The combined checks/render used 0.34 CPU / 0.34 wall seconds, peak 62,840 KiB RSS.

See `verification.json`, `checks.json` and the retained resource/stdout/stderr logs. To regenerate from the
same completed archive without simulation, run `.venv/bin/python results/resource_patch_population_explorer_20261016/render.py`.
The frozen source archive and current scientific study were not modified.

Root and independent review reconcile all identities, ranks, endpoint flags and displayed values. Final wording clarifies the historical AO scales; a second saved-data render passes the same mapping checks. Original check receipts remain under `initial_checks/`.
