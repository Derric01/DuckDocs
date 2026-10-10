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

The final rebuilt-image rerun (`phase-2-followup-rebuilt-final`) measured
`18, 15, 13, 12, 15, 16, 15, 14, 15, 11, 14, 17, 16` seconds for questions
1–13 respectively. Its aggregate remained 4 PASS, 3 PARTIAL, 6 FAIL, with
zero passing answers carrying a wrong or missing citation. All 13 questions
used the extractive fallback; Ollama received 26 generation requests, exactly
two per question, so the accepted structured-answer rate was 0/13 in this
run. This is an acceptance/verification result, not evidence that every
response failed JSON parsing.

## Phase 2 performance follow-up

The ask endpoint now runs synchronous RAG work in a worker thread, so normal
document/provider requests can continue while an ask is running. Ollama ask
requests explicitly set `num_predict=128`, `num_ctx=4096`, a 60-second HTTP
timeout, and `keep_alive=10m`. Ask prompts are limited to six passages of at
most 1,200 characters each; their estimated token count is logged at DEBUG
without logging query or document text. The scorecard timeout is 90 seconds,
with an abort after two consecutive timeouts. Its preflight requires exactly
15 unique Library filenames and no queued/processing ingest jobs.

The measured question-1 generation path made two Ollama calls before the
extractive fallback. Ollama reported approximately 5.7 seconds for the first
call and 7.3 seconds for the corrective call; both reached the generation
cap. Retrieval and prompt construction were not the bottleneck. The final
scorecard run used the rebuilt backend and an idle model:

| Question | Result | Cited | Chunks | Seconds | Provider | Answer start |
|---:|---|---|---:|---:|---|---|
| 1 | FAIL | NO | 12 | 14 | extractive evidence_synth | DuckDocs Test File - Native Text PDF This PDF has a rea |
| 2 | FAIL | NO | 12 | 17 | extractive evidence_synth | DuckDocs Test File - Scanned PDF (OCR) This page has No |
| 3 | PASS | yes | 12 | 23 | extractive evidence_synth | Temperature The annual average high temperature is 21.0 |
| 4 | PASS | yes | 12 | 14 | extractive evidence_synth | Page marker:SCAN-PAGE-2-b82e Use this file to test DUCK |
| 5 | PASS | yes | 12 | 18 | extractive evidence_synth | Slide 3 Slide 3: Final marker Test marker: PPTX-SLIDE3- |
| 6 | FAIL | NO | 12 | 17 | extractive evidence_synth | DuckDocs Test File - Word Document This DOCX tests para |
| 7 | PASS | yes | 12 | 16 | extractive evidence_synth | Section 3: Table Item Quantity Status Widget A 12 In st |
| 8 | FAIL | yes | 12 | 17 | extractive evidence_synth | Sheet: Sales Month \| Revenue \| Units Jan \| 12000 \| 340 |
| 9 | PARTIAL | yes | 12 | 18 | extractive evidence_synth | id \| name \| department \| salary 1 \| Asha Rao \| Engineer |
| 10 | PARTIAL | yes | 12 | 17 | extractive evidence_synth | test_file: 13-config.yaml purpose: structured extractio |
| 11 | PARTIAL | yes | 12 | 16 | extractive evidence_synth | <?xml version="1.0"?> <root> <marker>XML-MARKER-6f3c</m |
| 12 | FAIL | n/a | 12 | 17 | extractive evidence_synth | DuckDocs Test File - Native Text PDF This PDF has a rea |
| 13 | FAIL | n/a | 12 | 18 | extractive evidence_synth | DuckDocs Test File -ScannedPage l of 3 No text layer on |

**Aggregate:** 4 PASS, 3 PARTIAL, 6 FAIL; 0 passing answers with a
wrong/missing citation.

During a controlled retry of the native-text document, an ask overlapped an
active ingest and took 18.43 seconds versus 14 seconds for the same question
on the idle stack. The ingest emitted one summary generation call, confirming
that model summaries compete for the single local Ollama slot. A minimal next
step is to index and mark the document ready using its extractive summary
first, then queue the optional abstractive summary after indexing; that
keeps ask traffic from waiting behind summary generation.

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
