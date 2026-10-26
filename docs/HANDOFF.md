# TraceMind AI: frontend handoff, deployment and submission

Backend is done and tested (63 tests). Everything the UI needs is a real endpoint; **real response samples are in
`docs/api_examples/*.json`** (regenerate: `cd backend && python scripts/dump_api_examples.py`). Build and mock against those.

## 1. Run the backend locally
```bash
cd backend
python -m venv .venv && .venv\Scripts\activate      # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload                        # http://localhost:8000/docs
```
Frontend: Vite + React + TypeScript + Tailwind in `frontend/`, dev server on **http://localhost:5173** (already allowed by CORS).
Read the API base URL from `import.meta.env.VITE_API_URL` (default `http://localhost:8000`). No secrets in the frontend.

## 2. Pages -> endpoints
| Required view | Endpoints | Example file |
|---|---|---|
| Overview dashboard | `GET /api/benchmark` (headline metrics), `GET /api/benchmark/scenarios` | benchmark.json |
| Trace explorer (list / load examples) | `GET /api/benchmark/scenarios`, `POST /api/benchmark/scenarios/{id}/load`, `POST /api/traces` (file upload), `GET /api/tasks` | benchmark_scenarios.json, tasks.json |
| Trace detail + timeline | `GET /api/traces/{id}` (works for uploaded traces, loaded scenarios AND runs) | trace.json |
| Findings + evidence panel | `POST /api/traces/{id}/analyze` (or `/api/runs/{id}/analyze`), `GET /api/traces/{id}/findings` | analysis.json |
| Corrective action review | `GET /api/runs/{id}/corrections` | corrections.json |
| Baseline vs corrected comparison | `POST /api/runs/{id}/replay`, `GET /api/runs/{id}/comparison` | run_replayed.json, comparison.json |
| Benchmark results | `GET /api/benchmark` (live), `GET /api/benchmark/saved` | benchmark.json |
| Settings | none needed, see note below | |

Also: `POST /api/tasks/run` `{task_id}` creates a baseline run; `POST /api/tasks/evaluate` `{configuration}` runs all tasks under a candidate config
(use it to show a bad fix causing a regression: `{"configuration": {"max_retries": 0}}` -> `tasks_regressed: ["flaky_search_retry"]`).

**Settings page:** the backend has no LLM integration, the analysis is fully rule-based. Show that fact ("LLM explanations: not enabled, all
findings are rule-based") and do **not** build a fake API-key form or a toggle that does nothing.

## 3. Behaviour the UI must respect
- **Highlight evidence:** each finding has `evidence_event_ids`; highlight those `event_id`s in the timeline.
- **Facts vs hypotheses:** render `observed_facts` as "Observed in trace" and `likely_root_cause` as "Hypothesis" (plus `alternative_explanations`). Show `explanation_source` ("rule_based").
- **Approval is explicit:** replay requires `{"approved": true, "approved_changes": {...}}`. Pre-fill `approved_changes` from `combined_changes`, let the user untick individual corrections, and send only an explicit user approval. Never auto-replay.
- **Don't claim a fix works before replay.** `verification_status`: `detected` -> `fix_proposed` -> `fix_verified` | `fix_not_effective`. Only show "verified" when the API says `fix_verified`.
- **Regressions:** `comparison.regression === true` must be shown prominently (red), e.g. "Fix introduced a regression: success -> failure".
- **Label data sources:** `comparison.data_source` and `benchmark.data_source` / `runner_sweep.data_source` say where numbers come from. Show it. Durations are *simulated*; `token_usage` is `null` (show "not available").
- **`null` metrics** (precision/recall when undefined) must render as "n/a", never 0.
- **Honest benchmark display:** show held-out and dev rows separately, show `limitations`, and show the misses (`scenario_results` where `false_positives` / `false_negatives` is non-empty).
- **States:** loading, empty, success, error and malformed-upload for every view. Cold start can take ~1 minute on the free host, so show a "waking up the server" message after ~3 s.

## 4. Error shapes
- `400` / `404` / `413`: `{"detail": "message"}`
- `422`: `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}` (trace validation or bad replay config)
- Samples in `docs/api_examples/errors.json`.

## 5. Enums
- finding `category`: `repeated_call_no_progress`, `missing_required_step`, `invalid_action_sequence`, `explicit_tool_error`, `unsupported_completion_claim`, `evidence_constraint_contradiction`
- `severity`: `low` | `medium` | `high`
- event `event_type`: `tool_call` | `model_message` | `final_answer`
- `execution_status` / `agent_reported_status`: `completed` | `failed` | `incomplete`; run `task_outcome`: `success` | `failure`

## 6. Deploy
**Backend (Render free web service, Docker).** `Dockerfile` and `render.yaml` are at the repo root (they must be: the backend reads `../benchmarks`).
1. Push the repo to a public GitHub repo.
2. Render -> New -> Blueprint (or Web Service, runtime Docker) -> select the repo. Health check path `/api/health`.
3. Set env var `CORS_ORIGINS` = your frontend URL (no trailing slash). Redeploy.
4. Open `https://<service>.onrender.com/docs` and `/api/health`.

**Frontend (Vercel).** Root directory `frontend`, build `npm run build`, output `dist`, env `VITE_API_URL=https://<service>.onrender.com`.
Then put the Vercel URL into Render's `CORS_ORIGINS`. For preview URLs optionally set `CORS_ORIGIN_REGEX`.

**Free-tier behaviour (checked against Render's docs):** a free web service spins down after 15 minutes without traffic and takes about a
minute to wake; local files, including the SQLite database, are wiped on restart/spin-down. Consequences: (a) **open the site and run through the
demo 2 minutes before you record or submit** so it is awake; (b) data does not persist, so always start from the built-in examples
(`POST /api/benchmark/scenarios/{id}/load`, `POST /api/tasks/run`); (c) keep a fallback: record the demo against `localhost` if the host is down.

## 7. Demo script (about 2 min, matches the required structure)
| Time | Show |
|---|---|
| 0:00-0:15 | Problem: agents fail silently (repeat calls, claim success on empty data). Nobody wants to read raw logs. |
| 0:15-0:40 | Trace explorer -> load scenario **D03** (or run task `refund_empty_search`). Timeline shows the same search 3x with empty results, then "Task complete". |
| 0:40-1:00 | Analyze -> two findings; click one, evidence events highlight. Point out *Observed* vs *Hypothesis*. |
| 1:00-1:25 | Corrective action review -> approve -> replay. New run searches "refund policy" then "refunds", finds the doc, succeeds. |
| 1:25-1:45 | Comparison: failure -> success, tool calls 4 -> 3, findings resolved, `fix_verified`. Then show a bad fix (`max_retries: 0`) flagged as a regression. |
| 1:45-2:00 | Benchmark page: 28 labelled scenarios, held-out precision 0.857 / recall 0.750, with the 3 known misses listed. "Rule-based, no LLM needed, measured not claimed." |

Say clearly in the video: the runner is a deterministic simulated agent, the benchmark is small (28 scenarios), the held-out set is not blind.

## 8. Pre-submission checklist
- [ ] Public GitHub repo, no `.env`, no `*.db`, no `node_modules` committed
- [ ] `pytest -q` passes (63 tests) and `python -m app.evaluation.run_benchmark` prints the same table as the README
- [ ] Backend URL: `/api/health` returns ok; `/docs` loads
- [ ] Frontend URL loads, works end to end against the deployed backend (load example -> analyze -> approve -> replay -> comparison -> benchmark)
- [ ] README: replace the `TODO` deployment links, demo video link and team contributions
- [ ] Demo video recorded on the working app (about 2 min), link opens without login
- [ ] All four links submitted (project, GitHub, live site, video) before the portal deadline, and re-opened from an incognito window
