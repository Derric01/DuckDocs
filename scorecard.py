#!/usr/bin/env python3
"""DuckDocs scorecard: asks the 13 test questions via POST /api/v1/ask and grades them.

Usage:
    python scorecard.py --label veera-merged
    python scorecard.py --label after-fix --url http://localhost:8000
    python scorecard.py --label retry --only 1,4,7

Standard library only. It talks to localhost, so nothing leaves your machine.
Upload the 15 test files first and wait until each shows Ready in the Library.
Uses the real GroundedResponse fields: outcome, answer, grounded, citations,
provider, retrieved_chunk_count, refusal_reason.
"""
import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
import socket

REFUSAL_TEXT_HINTS = ("not enough evidence", "insufficient_evidence", "insufficient evidence")

# must: regexes that must ALL match the answer text (otherwise FAIL)
# must_not: regexes that downgrade a correct answer to PARTIAL (raw dumps, extra rows)
# cite: regexes that must ALL match the cited snippets (defaults to must)
CASES = [
    {"id": 1, "q": "What is the test marker in the native text PDF?",
     "must": [r"NATIVE-PDF-7f3a2b"]},
    {"id": 2, "q": "What does the scanned OCR PDF say?",
     "must": [r"SCAN-PDF-9d1c4e|rendered image embedded in a PDF"]},
    {"id": 3, "q": "What is the annual average high temperature in Kyoto?",
     "must": [r"21\.0"]},
    {"id": 4, "q": "What is the marker on page 2 of the scanned multi-page document?",
     "must": [r"SCAN-PAGE-2-b82e"]},
    {"id": 5, "q": "What's written in the presentation's third slide?",
     "must": [r"PPTX-SLIDE3-ce02"]},
    {"id": 6, "q": "What does the paragraph on the second page of the Word document say?",
     "must": [r"new page|page-break awareness"]},
    {"id": 7, "q": "How many units of Widget A are in stock?",
     "must": [r"\b12\b"], "cite": [r"Widget A"]},
    {"id": 8, "q": "What was the total revenue across January, February, and March in the sales spreadsheet?",
     "must": [r"37,?300"], "cite": [r"15,?500"]},
    {"id": 9, "q": "Which employees work in the Engineering department and what are their salaries?",
     "must": [r"Asha Rao.*85,?000", r"Priya Nair.*91,?000"], "must_not": [r"Marcus Lee"],
     "cite": [r"Asha Rao", r"Priya Nair"]},
    {"id": 10, "q": "What's the marker value in the YAML config file?",
     "must": [r"YAML-MARKER-2d9b"], "must_not": [r"structured extraction test"]},
    {"id": 11, "q": "What items are listed in the XML file?",
     "must": [r"First", r"Second"], "must_not": [r"<root>|<item"]},
    {"id": 12, "q": "What is DuckDocs' pricing model?", "refusal": True},
    {"id": 13, "q": "Who is the CEO of DuckDocs?", "refusal": True},
]


def ask(base, query, timeout):
    body = json.dumps({"query": query, "stream": False}).encode("utf-8")
    req = urllib.request.Request(
        base.rstrip("/") + "/api/v1/ask", data=body,
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_json(base, path, timeout):
    req = urllib.request.Request(base.rstrip("/") + path, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def preflight(base, timeout):
    documents = get_json(base, "/api/v1/documents?limit=100", timeout).get("items", [])
    if len(documents) != 15:
        raise RuntimeError(f"Scorecard aborted: expected 15 documents in the Library, found {len(documents)}.")
    names = [str(document.get("name", "")).casefold() for document in documents]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise RuntimeError(f"Scorecard aborted: duplicate Library filename(s): {', '.join(duplicates)}.")
    jobs = get_json(base, "/api/v1/ingest-jobs", timeout)
    active = [job.get("id", "unknown") for job in jobs if job.get("status") in {"queued", "processing"}]
    if active:
        raise RuntimeError(f"Scorecard aborted: ingest job(s) still active: {', '.join(active)}.")


def split_response(resp):
    """Return (answer_text, refused, citation_snippets, citation_count)."""
    citations = resp.get("citations") or []
    snippets = " ".join(str(c.get("snippet", "")) for c in citations if isinstance(c, dict))
    answer = resp.get("answer") if isinstance(resp.get("answer"), str) else ""
    refused = resp.get("outcome") == "insufficient_evidence" or not answer.strip()
    if not refused and any(h in answer.lower() for h in REFUSAL_TEXT_HINTS):
        refused = True
    return answer, refused, snippets, len(citations)


def matches_all(patterns, text):
    return all(re.search(p, text, re.IGNORECASE | re.DOTALL) for p in patterns)


def grade(case, resp):
    """Return (result, cited, shown_text)."""
    answer, refused, snippets, _ = split_response(resp)
    shown = answer if answer.strip() else f"[refused: {resp.get('refusal_reason') or 'no reason given'}]"
    if case.get("refusal"):
        return ("PASS" if refused else "FAIL"), "n/a", shown
    if refused:
        return "FAIL", "NO", shown
    cite_ok = "yes" if matches_all(case.get("cite", case["must"]), snippets) else "NO"
    if cite_ok == "NO":
        return "FAIL", cite_ok, shown
    if not matches_all(case["must"], answer):
        return "FAIL", cite_ok, shown
    if any(re.search(p, answer, re.IGNORECASE) for p in case.get("must_not", [])):
        return "PARTIAL", cite_ok, shown
    return "PASS", cite_ok, shown


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default="http://localhost:8000")
    parser.add_argument("--label", default="run")
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--only", default="", help="comma-separated question numbers, e.g. 1,4,7")
    args = parser.parse_args()

    wanted = {int(x) for x in args.only.split(",") if x.strip()}
    cases = [c for c in CASES if not wanted or c["id"] in wanted]
    results, raw = [], {}

    try:
        preflight(args.url, args.timeout)
    except Exception as err:
        print(str(err), file=sys.stderr)
        return 2

    print(f"Scorecard '{args.label}' against {args.url}\n")
    print(f"{'#':>2}  {'Result':<8}{'Cited':<6}{'Chunks':>6}{'Secs':>6}  {'Provider':<26}Answer")
    print("-" * 110)
    consecutive_timeouts = 0
    for case in cases:
        started = time.time()
        chunks, provider = "?", ""
        abort_after_case = False
        try:
            resp = ask(args.url, case["q"], args.timeout)
            result, cited, shown = grade(case, resp)
            chunks = resp.get("retrieved_chunk_count", "?")
            provider_info = resp.get("provider") or {}
            if isinstance(provider_info, dict):
                provider = f"{provider_info.get('name', '')} {provider_info.get('model', '')}".strip()
            else:
                provider = str(provider_info)
            raw[case["id"]] = resp
            consecutive_timeouts = 0
        except urllib.error.HTTPError as err:
            result, cited = "FAIL", "n/a"
            shown = f"HTTP {err.code}: {err.read().decode('utf-8', 'replace')[:80]}"
            raw[case["id"]] = {"error": shown}
        except (socket.timeout, TimeoutError) as err:
            result, cited, shown = "FAIL", "n/a", f"TIMEOUT: {err}"
            raw[case["id"]] = {"error": str(err), "timeout": True}
            consecutive_timeouts += 1
            if consecutive_timeouts >= 2:
                print("Scorecard aborted: 2 consecutive question timeouts.", file=sys.stderr)
                abort_after_case = True
        except urllib.error.URLError as err:
            if isinstance(err.reason, (socket.timeout, TimeoutError)):
                result, cited, shown = "FAIL", "n/a", f"TIMEOUT: {err}"
                raw[case["id"]] = {"error": str(err), "timeout": True}
                consecutive_timeouts += 1
                if consecutive_timeouts >= 2:
                    print("Scorecard aborted: 2 consecutive question timeouts.", file=sys.stderr)
                    abort_after_case = True
            else:
                result, cited, shown = "FAIL", "n/a", f"ERROR: {err}"
                raw[case["id"]] = {"error": str(err)}
                consecutive_timeouts = 0
        except Exception as err:  # connection refused, bad JSON
            result, cited, shown = "FAIL", "n/a", f"ERROR: {err}"
            raw[case["id"]] = {"error": str(err)}
            consecutive_timeouts = 0
        elapsed = time.time() - started
        one_line = " ".join(shown.split())[:55]
        print(f"{case['id']:>2}  {result:<8}{cited:<6}{chunks!s:>6}{elapsed:>6.0f}  {provider[:25]:<26}{one_line}")
        results.append((case["id"], result, cited))
        if abort_after_case:
            break

    passes = sum(1 for _, r, _ in results if r == "PASS")
    partial = sum(1 for _, r, _ in results if r == "PARTIAL")
    fails = sum(1 for _, r, _ in results if r == "FAIL")
    bad_cites = sum(1 for _, r, c in results if c == "NO" and r != "FAIL")
    print("-" * 110)
    print(f"PASS {passes}   PARTIAL {partial}   FAIL {fails}   of {len(results)}"
          f"   |   passing answers with a wrong/missing citation: {bad_cites}")

    out_file = f"scorecard_{args.label}.json"
    with open(out_file, "w", encoding="utf-8") as fh:
        json.dump({"label": args.label, "results": results, "raw": raw}, fh, indent=2, ensure_ascii=False)
    print(f"Raw responses saved to {out_file}")


if __name__ == "__main__":
    raise SystemExit(main())
