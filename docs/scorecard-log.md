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

## Phase 1 fixed-script baseline

After the scorecard citation grading and provider display fixes, the 13
questions were run twice sequentially. The two runs had the same aggregate
result, while retaining both measurements because the 1B model can vary.

### Fixed-script run 1

| Question | Result | Cited | Chunks | Seconds | Answer start |
|---:|---|---|---:|---:|---|
| 1 | FAIL | NO | 10 | 3 | Question: What is the test marker in the native text PD |
| 2 | FAIL | NO | 7 | 5 | DuckDocs Test File - Scanned PDF (OCR) This page has No |
| 3 | FAIL | NO | 6 | 2 | What is the annual average high temperature in Kyoto? |
| 4 | FAIL | NO | 7 | 4 | I am DuckDocs Waymark. |
| 5 | PASS | yes | 6 | 6 | Slide 3 Slide 3: Final marker Test marker: PPTX-SLIDE3- |
| 6 | FAIL | NO | 6 | 5 | DuckDocs Test File - Word Document This DOCX tests para |
| 7 | PASS | yes | 6 | 4 | Section 3: Table Item Quantity Status Widget A 12 In st |
| 8 | FAIL | NO | 6 | 4 | The record identifies the Engineering department. |
| 9 | PARTIAL | yes | 6 | 5 | id \| name \| department \| salary 1 \| Asha Rao \| Engineer |
| 10 | PARTIAL | yes | 7 | 4 | test_file: 13-config.yaml purpose: structured extractio |
| 11 | PARTIAL | yes | 6 | 4 | <?xml version="1.0"?> <root> <marker>XML-MARKER-6f3c</m |
| 12 | FAIL | n/a | 6 | 3 | I am DuckDocs Waymark. |
| 13 | FAIL | n/a | 7 | 5 | DuckDocs Test File -ScannedPage l of 3 No text layer on |

**Aggregate:** 2 PASS, 3 PARTIAL, 8 FAIL; 0 passing answers with a
wrong/missing citation.

## Phase 2 citation-integrity result

Phase 2 added structured claim/quote verification, fail-closed handling for
unverified output, deterministic Ollama ask settings (`temperature=0`,
`seed=0`), junk-output rejection, and source-bound citation construction.
The pre-change comparison is the two fixed-script Phase 1 runs above.

### Phase 2 run 1

| Question | Result | Cited | Chunks | Seconds | Provider | Answer start |
|---:|---|---|---:|---:|---|---|
| 1 | FAIL | NO | 10 | 3 | ollama llama3.2:1b | Question: What is the test marker in the native text PD |
| 2 | FAIL | NO | 7 | 5 | extractive evidence_synth | DuckDocs Test File - Scanned PDF (OCR) This page has No |
| 3 | FAIL | NO | 6 | 2 | ollama llama3.2:1b | What is the annual average high temperature in Kyoto? |
| 4 | FAIL | NO | 7 | 6 | ollama llama3.2:1b | I am DuckDocs Waymark. |
| 5 | PASS | yes | 6 | 6 | extractive evidence_synth | Slide 3 Slide 3: Final marker Test marker: PPTX-SLIDE3- |
| 6 | FAIL | NO | 6 | 6 | extractive evidence_synth | DuckDocs Test File - Word Document This DOCX tests para |
| 7 | PASS | yes | 6 | 4 | extractive evidence_synth | Section 3: Table Item Quantity Status Widget A 12 In st |
| 8 | FAIL | NO | 6 | 4 | ollama llama3.2:1b | The record identifies the Engineering department. |
| 9 | PARTIAL | yes | 6 | 5 | extractive evidence_synth | id \| name \| department \| salary 1 \| Asha Rao \| Engineer |
| 10 | PARTIAL | yes | 7 | 5 | extractive evidence_synth | test_file: 13-config.yaml purpose: structured extractio |
| 11 | PARTIAL | yes | 6 | 4 | extractive evidence_synth | <?xml version="1.0"?> <root> <marker>XML-MARKER-6f3c</m |
| 12 | FAIL | n/a | 6 | 3 | ollama llama3.2:1b | I am DuckDocs Waymark. |
| 13 | FAIL | n/a | 7 | 5 | extractive evidence_synth | DuckDocs Test File -ScannedPage l of 3 No text layer on |

**Aggregate:** 2 PASS, 3 PARTIAL, 8 FAIL; 0 passing answers with a
wrong/missing citation.

### Phase 2 run 2

| Question | Result | Cited | Chunks | Seconds | Provider | Answer start |
|---:|---|---|---:|---:|---|---|
| 1 | FAIL | NO | 10 | 3 | ollama llama3.2:1b | Question: What is the test marker in the native text PD |
| 2 | FAIL | NO | 7 | 5 | extractive evidence_synth | DuckDocs Test File - Scanned PDF (OCR) This page has No |
| 3 | FAIL | NO | 6 | 2 | ollama llama3.2:1b | What is the annual average high temperature in Kyoto? |
| 4 | FAIL | NO | 7 | 5 | ollama llama3.2:1b | I am DuckDocs Waymark. |
| 5 | PASS | yes | 6 | 6 | extractive evidence_synth | Slide 3 Slide 3: Final marker Test marker: PPTX-SLIDE3- |
| 6 | FAIL | NO | 6 | 6 | extractive evidence_synth | DuckDocs Test File - Word Document This DOCX tests para |
| 7 | PASS | yes | 6 | 4 | extractive evidence_synth | Section 3: Table Item Quantity Status Widget A 12 In st |
| 8 | FAIL | NO | 6 | 4 | ollama llama3.2:1b | The record identifies the Engineering department. |
| 9 | PARTIAL | yes | 6 | 5 | extractive evidence_synth | id \| name \| department \| salary 1 \| Asha Rao \| Engineer |
| 10 | PARTIAL | yes | 7 | 5 | extractive evidence_synth | test_file: 13-config.yaml purpose: structured extractio |
| 11 | PARTIAL | yes | 6 | 5 | extractive evidence_synth | <?xml version="1.0"?> <root> <marker>XML-MARKER-6f3c</m |
| 12 | FAIL | n/a | 6 | 4 | ollama llama3.2:1b | I am DuckDocs Waymark. |
| 13 | FAIL | n/a | 7 | 5 | extractive evidence_synth | DuckDocs Test File -ScannedPage l of 3 No text layer on |

**Aggregate:** 2 PASS, 3 PARTIAL, 8 FAIL; 0 passing answers with a
wrong/missing citation.

### Fixed-script run 2

| Question | Result | Cited | Chunks | Seconds | Answer start |
|---:|---|---|---:|---:|---|
| 1 | FAIL | NO | 10 | 3 | Question: What is the test marker in the native text PD |
| 2 | FAIL | NO | 7 | 5 | DuckDocs Test File - Scanned PDF (OCR) This page has No |
| 3 | FAIL | NO | 6 | 2 | What is the annual average high temperature in Kyoto? |
| 4 | FAIL | NO | 7 | 4 | I am DuckDocs Waymark. |
| 5 | PASS | yes | 6 | 6 | Slide 3 Slide 3: Final marker Test marker: PPTX-SLIDE3- |
| 6 | FAIL | NO | 6 | 6 | DuckDocs Test File - Word Document This DOCX tests para |
| 7 | PASS | yes | 6 | 4 | Section 3: Table Item Quantity Status Widget A 12 In st |
| 8 | FAIL | NO | 6 | 4 | The record identifies the Engineering department. |
| 9 | PARTIAL | yes | 6 | 5 | id \| name \| department \| salary 1 \| Asha Rao \| Engineer |
| 10 | PARTIAL | yes | 7 | 4 | test_file: 13-config.yaml purpose: structured extractio |
| 11 | PARTIAL | yes | 6 | 4 | <?xml version="1.0"?> <root> <marker>XML-MARKER-6f3c</m |
| 12 | FAIL | n/a | 6 | 3 | I am DuckDocs Waymark. |
| 13 | FAIL | n/a | 7 | 5 | DuckDocs Test File -ScannedPage l of 3 No text layer on |

**Aggregate:** 2 PASS, 3 PARTIAL, 8 FAIL; 0 passing answers with a
wrong/missing citation.
