# Scorecard Log

The scorecard is a measurement tool, not an implementation specification.
Expected patterns remain in [`scorecard.py`](../scorecard.py); application
behavior must be fixed generically rather than for individual fixture strings.

## Phase 0 live baseline

Run against the existing stack before Phase 1 changes, with the original
question 6 wording:

> What does the second paragraph after the page break say in the Word document?

| Result | PASS | PARTIAL | FAIL | Passing answers with wrong/missing citation |
|---|---:|---:|---:|---:|
| Phase 0 baseline | 1 | 2 | 10 | 0 |

Per-question duration in seconds, questions 1–13:

`23, 7, 19, 10, 10, 23, 10, 11, 13, 17, 31, 48, 11`

Question 6 returned a fail and the answer began:

> Second paragraph with a page break coming next.

This run was labeled `phase-0`; its raw output was inspected and the temporary
JSON artifact was removed after recording the results.

## Phase 1 baseline

Phase 1 changes the wording of question 6 to:

> What does the paragraph on the second page of the Word document say?

The expected answer pattern is unchanged:

`new page|page-break awareness`

The measured result and per-question durations will be recorded below after
running `python scorecard.py --label phase-1`.

| Result | PASS | PARTIAL | FAIL | Passing answers with wrong/missing citation |
|---|---:|---:|---:|---:|
| Phase 1 baseline | 1 | 2 | 10 | 0 |

Per-question duration in seconds, questions 1–13:

`21, 7, 19, 10, 11, 24, 10, 11, 12, 17, 30, 47, 11`

Question 6 returned a fail and the answer began:

> DuckDocs Test File - Word Document This DOCX tests paragraph

The wording change therefore affects the measured prompt and response, but
does not yet fix DOCX page-aware retrieval; that is reserved for Phase 6.
