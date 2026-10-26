"""Generates benchmarks/scenarios/*.json. Ground truth is hand-labelled here, independent of the detectors.
Run from the repo root: python benchmarks/generate_scenarios.py"""
import json
import pathlib

OUT = pathlib.Path(__file__).parent / "scenarios"
OUT.mkdir(exist_ok=True)

DOC = {"results": [{"title": "Refund Policy", "text": "Refunds are available within 30 days."}]}
EMPTY = {"results": []}
SUM = {"summary": "Refunds are available within 30 days."}
RP = {"query": "refund policy"}
FIXES = {
    "repeated_call_no_progress": "Cap retries and change the input (or stop) after an unchanged result.",
    "missing_required_step": "Block completion until all required steps have succeeded.",
    "invalid_action_sequence": "Enforce the prerequisite order between the two actions.",
    "explicit_tool_error": "Validate inputs and handle the error (bounded retry, fallback, or report failure).",
    "unsupported_completion_claim": "Require evidence (non-empty retrieval, successful final step) before declaring completion.",
    "evidence_constraint_contradiction": "Check tool outputs against task constraints before declaring completion.",
}


def c(tool, inp, out=None, err=None):
    return ("call", tool, inp, out, err)


def fin(text):
    return ("final", text)


def build(sid, slug, split, desc, outcome, truth, steps, status="completed", config=None, notes=""):
    events = []
    for n, s in enumerate(steps, start=1):
        base = {"event_id": f"e{n}", "step_number": n, "timestamp": f"2026-10-12T10:{n // 60:02d}:{n % 60:02d}Z", "duration_ms": 100}
        if s[0] == "call":
            _, tool, inp, out, err = s
            events.append({**base, "event_type": "tool_call", "tool_name": tool, "input": inp, "output": out, "error_details": err})
        else:
            events.append({**base, "event_type": "final_answer", "output": s[1], "duration_ms": 0})
    behavior = ("No finding expected." if not truth else
                "; ".join(f"Flag {cat} citing {ids}" for cat, ids in truth.items()) + ".")
    correction = ("None needed." if not truth else " ".join(FIXES[cat] for cat in truth))
    doc = {
        "scenario_id": sid, "split": split, "description": desc, "notes": notes,
        "expected_task_outcome": outcome, "ground_truth_failures": truth,
        "expected_detector_behavior": behavior, "expected_correction": correction,
        "trace": {"run_id": f"{sid}-{slug}", "task_description": desc, "initial_configuration": config or {},
                  "execution_status": status, "events": events},
    }
    (OUT / f"{sid}_{slug}.json").write_text(json.dumps(doc, indent=2))


ORDER_CFG = {"required_steps": ["validate_input", "execute_order"], "sequence_rules": [["validate_input", "execute_order"]]}
SEARCH_FIRST = {"sequence_rules": [["search_docs", "summarize"]]}
FLIGHT = [{"tool": "search_flights", "field": "price", "max": 500}]
D = "dev"
H = "heldout"

# ---------------- development set (used while designing the rules) ----------------
build("D01", "clean_lookup", D, "Find the refund policy and summarize it.", "success", {},
      [c("search_docs", RP, DOC), c("summarize", {"text": DOC["results"][0]["text"]}, SUM), fin("Task complete: refunds within 30 days.")])
build("D02", "clean_order_flow", D, "Validate, execute and receipt an order.", "success", {},
      [c("validate_input", {"order": "A1"}, {"valid": True}), c("execute_order", {"order": "A1"}, {"id": "X9"}),
       c("send_receipt", {"order": "A1"}, {"sent": True}), fin("Task complete: order A1 placed.")],
      config={**ORDER_CFG, "required_steps": ["validate_input", "execute_order", "send_receipt"]})
build("D03", "repeated_empty_claim", D, "Find the refund policy and summarize it.", "failure",
      {"repeated_call_no_progress": ["e1", "e2", "e3"], "unsupported_completion_claim": ["e4", "e5"]},
      [c("search_docs", RP, EMPTY)] * 3 + [c("summarize", {"text": ""}, SUM), fin("Task complete: refunds within 30 days.")])
build("D04", "repeated_errors_five", D, "Find the refund policy and summarize it.", "failure",
      {"repeated_call_no_progress": ["e1", "e2", "e3", "e4", "e5"], "explicit_tool_error": ["e1"]},
      [c("search_docs", RP, None, "503 timeout")] * 5 + [fin("Task failed: search service unavailable.")], status="failed")
build("D05", "legit_retry_recovered", D, "Find the refund policy and summarize it.", "success",
      {"explicit_tool_error": ["e1"]},
      [c("search_docs", RP, None, "503 timeout"), c("search_docs", RP, DOC),
       c("summarize", {"text": DOC["results"][0]["text"]}, SUM), fin("Task complete: refunds within 30 days.")],
      notes="Legitimate retry: the error is recorded, but the retry must NOT be flagged as a repeated call.")
build("D06", "polling_progress", D, "Wait for job 7 to finish.", "success", {},
      [c("check_job", {"id": 7}, {"status": "pending"}), c("check_job", {"id": 7}, {"status": "pending"}),
       c("check_job", {"id": 7}, {"status": "done"}), fin("Task complete: job 7 finished.")],
      notes="Legitimate polling: the result changes, so no failure.")
build("D07", "changing_queries_all_empty", D, "Find the refund policy and summarize it.", "failure",
      {"unsupported_completion_claim": ["e5", "e6"]},
      [c("search_docs", {"query": q}, EMPTY) for q in ("refund policy", "refunds", "return policy", "money back")]
      + [c("summarize", {"text": ""}, SUM), fin("Task complete: refunds within 30 days.")],
      notes="Inputs change each time, so this is not a repeated call; the unsupported claim is the failure.")
build("D08", "unrecovered_error_claim", D, "Find the refund policy and summarize it.", "failure",
      {"explicit_tool_error": ["e1"], "unsupported_completion_claim": ["e1", "e2"]},
      [c("search_docs", RP, None, "401 unauthorized"), fin("Task complete: I looked up the refund policy.")])
build("D09", "honest_failure", D, "Find the refund policy and summarize it.", "failure",
      {"explicit_tool_error": ["e1"]},
      [c("search_docs", RP, None, "503 service unavailable"), fin("Task failed: service unavailable.")], status="failed")
build("D10", "skipped_validation", D, "Validate and execute an order.", "failure",
      {"missing_required_step": ["e2"]},
      [c("execute_order", {"order": "A1"}, {"id": "X9"}), fin("Task complete: order placed.")],
      config={"required_steps": ["validate_input", "execute_order"]})
build("D11", "required_steps_satisfied", D, "Validate and execute an order.", "success", {},
      [c("validate_input", {"order": "A1"}, {"valid": True}), c("execute_order", {"order": "A1"}, {"id": "X9"}),
       fin("Task complete: order placed.")], config={"required_steps": ["validate_input", "execute_order"]})
build("D12", "summarize_before_search", D, "Find the refund policy and summarize it.", "failure",
      {"invalid_action_sequence": ["e1"]},
      [c("summarize", {"text": "Refunds are available within 30 days."}, SUM), c("search_docs", RP, DOC),
       fin("Task complete: refunds within 30 days.")], config=SEARCH_FIRST)
build("D13", "valid_sequence", D, "Find the refund policy and summarize it.", "success", {},
      [c("search_docs", RP, DOC), c("summarize", {"text": DOC["results"][0]["text"]}, SUM),
       fin("Task complete: refunds within 30 days.")], config=SEARCH_FIRST)
build("D14", "price_over_budget", D, "Book a flight to BOM under 500.", "failure",
      {"evidence_constraint_contradiction": ["e1", "e3"]},
      [c("search_flights", {"to": "BOM"}, {"price": 720, "flight": "AI101"}), c("book_flight", {"flight": "AI101"}, {"booked": True}),
       fin("Booked AI101 for 720. Task complete.")], config={"constraints": FLIGHT})
build("D15", "price_within_budget", D, "Book a flight to BOM under 500.", "success", {},
      [c("search_flights", {"to": "BOM"}, {"price": 450, "flight": "AI202"}), c("book_flight", {"flight": "AI202"}, {"booked": True}),
       fin("Booked AI202 for 450. Task complete.")], config={"constraints": FLIGHT})
build("D16", "single_empty_claim", D, "Find the refund policy and summarize it.", "failure",
      {"unsupported_completion_claim": ["e2", "e3"]},
      [c("search_docs", RP, EMPTY), c("summarize", {"text": ""}, SUM), fin("Task complete: refunds within 30 days.")])
build("D17", "missing_and_invalid", D, "Validate and execute an order.", "failure",
      {"missing_required_step": ["e2"], "invalid_action_sequence": ["e1"]},
      [c("execute_order", {"order": "A1"}, {"id": "X9"}), fin("Task complete: order placed.")], config=ORDER_CFG)
build("D18", "two_identical_calls", D, "Find the refund policy and summarize it.", "success", {},
      [c("search_docs", RP, DOC), c("search_docs", RP, DOC), c("summarize", {"text": DOC["results"][0]["text"]}, SUM),
       fin("Task complete: refunds within 30 days.")], notes="Two identical successful calls: below the repeat threshold.")

# ---------------- held-out set (written after the detectors were frozen) ----------------
build("H01", "timeout_giveup", H, "Find the refund policy and summarize it.", "failure",
      {"repeated_call_no_progress": ["e1", "e2", "e3", "e4"], "explicit_tool_error": ["e1"]},
      [c("search_docs", RP, None, "timeout")] * 4 + [fin("Task failed: gave up after repeated timeouts.")], status="failed")
build("H02", "clean_three_step", H, "Fetch, validate and report data.", "success", {},
      [c("fetch_data", {"src": "db"}, {"rows": 10}), c("validate_data", {"rows": 10}, {"valid": True}),
       c("report", {"rows": 10}, {"ok": True}), fin("Task complete: report sent.")],
      config={"required_steps": ["fetch_data", "validate_data", "report"],
              "sequence_rules": [["fetch_data", "validate_data"], ["validate_data", "report"]]})
build("H03", "retry_with_fixed_input", H, "Parse the delivery date.", "success",
      {"explicit_tool_error": ["e1"]},
      [c("parse_date", {"text": "2026-13-45"}, None, "invalid date"), c("parse_date", {"text": "2026-10-13"}, {"date": "2026-10-13"}),
       fin("Task complete: delivery on 2026-10-13.")], notes="Recovered error with a corrected input.")
build("H04", "missing_validation", H, "Fetch, validate and report data.", "failure",
      {"missing_required_step": ["e3"]},
      [c("fetch_data", {"src": "db"}, {"rows": 10}), c("report", {"rows": 10}, {"ok": True}), fin("Task complete: report sent.")],
      config={"required_steps": ["fetch_data", "validate_data", "report"]})
build("H05", "authenticate_late", H, "Fetch customer records.", "failure",
      {"invalid_action_sequence": ["e1"]},
      [c("fetch_records", {"customer": 5}, {"records": 3}), c("authenticate", {"user": "bot"}, {"token": "t"}),
       fin("Task complete: records fetched.")], config={"sequence_rules": [["authenticate", "fetch_records"]]})
build("H06", "premium_over_budget", H, "Get an insurance quote with premium at most 200.", "failure",
      {"evidence_constraint_contradiction": ["e1", "e2"]},
      [c("get_quote", {"plan": "basic"}, {"premium": 260}), fin("Quote obtained within budget. Done.")],
      config={"constraints": [{"tool": "get_quote", "field": "premium", "max": 200}]})
build("H07", "alternating_loop", H, "Find the returns page.", "failure",
      {"repeated_call_no_progress": ["e1", "e2", "e3", "e4", "e5", "e6"]},
      [c("search_docs", {"query": "returns page"}, {"count": 0, "note": "no match"}),
       c("fetch_page", {"url": "https://example.test/returns"}, {"status": 404})] * 3
      + [fin("Task failed: could not find the returns page.")], status="failed",
      notes="Alternating identical calls with unchanged results: a loop, but not consecutive.")
build("H08", "failed_output_claimed_success", H, "Email the invoice to the customer.", "failure",
      {"unsupported_completion_claim": ["e1", "e2"]},
      [c("send_email", {"to": "a@b.test"}, {"status": "failed", "reason": "mailbox full"}), fin("Email sent successfully. Task complete.")],
      notes="The failure is in the tool OUTPUT, not in error_details.")
build("H09", "legit_empty_optional_arg", H, "Check whether any documents match 'zebra refund'.", "success", {},
      [c("search_docs", {"query": "zebra refund"}, EMPTY), c("log_event", {"note": ""}, {"logged": True}),
       fin("No matching documents were found; nothing to summarize. Task complete.")],
      notes="No results is a legitimate answer and the empty argument is optional.")
build("H10", "clean_shipping_lookup", H, "Find the shipping policy and summarize it.", "success", {},
      [c("search_docs", {"query": "shipping policy"}, {"results": [{"title": "Shipping", "text": "Orders ship within 2 business days."}]}),
       c("summarize", {"text": "Orders ship within 2 business days."}, {"summary": "Orders ship within 2 business days."}),
       fin("Task complete: orders ship within 2 business days.")])
print("wrote", len(list(OUT.glob("*.json"))), "scenarios")
