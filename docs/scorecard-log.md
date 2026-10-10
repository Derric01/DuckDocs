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

## Phase 4 retrieval and query-hint run

Phase 4 uses reciprocal rank fusion (RRF) for vector and keyword results.
Keyword-only results remain eligible when vector results exist, and vector
`min_similarity` filtering occurs before fusion. Generic query hints boost or
validate file formats and page/slide metadata. OCR page numbering was verified
against the existing parser remapping and required no parser change. The
optional built-in lexical reranker remains disabled by default
(`DUCKDOCS_RERANKER=off`); no additional model or dependency was added.

The backend image was rebuilt before each run. Both runs below were made with
the stack idle and produced identical results:

| Question | Result | Cited | Sources | Provider | Chunks | Seconds | Answer start |
|---:|---|---|---|---|---:|---:|---|
| 1 | FAIL | NO | n/a | extractive evidence_synth | 12 | 3 | [refused: citation_density_low] |
| 2 | FAIL | yes | 02-scanned-ocr.pdf, 03-scanned-multipage.pdf | ollama llama3.2:1b | 12 | 3 | The test marker in the scanned OCR PDF is SCAN-PDF-9d1c |
| 3 | PASS | yes | Kyoto_Japan_itinerary.pdf | ollama llama3.2:1b | 12 | 3 | The annual average high temperature in Kyoto is 21.0°C |
| 4 | PASS | yes | 03-scanned-multipage.pdf | extractive evidence_synth | 12 | 3 | Page marker:SCAN-PAGE-2-b82e Use this file to test DUCK |
| 5 | FAIL | yes | 08-presentation.pptx | ollama llama3.2:1b | 11 | 2 | Slide 3. |
| 6 | FAIL | NO | 06-document.docx | extractive evidence_synth | 11 | 2 | DuckDocs Test File - Word Document This DOCX tests para |
| 7 | PASS | yes | 07-spreadsheet.xlsx | extractive evidence_synth | 12 | 3 | Sheet: Inventory SKU \| Item \| Stock A-100 \| Widget A \| |
| 8 | FAIL | yes | 07-spreadsheet.xlsx | extractive evidence_synth | 12 | 2 | Sheet: Sales Month \| Revenue \| Units Jan \| 12000 \| 340 |
| 9 | PARTIAL | yes | 09-data.csv | extractive evidence_synth | 11 | 3 | id \| name \| department \| salary 1 \| Asha Rao \| Engineer |
| 10 | PARTIAL | yes | 13-config.yaml | extractive evidence_synth | 12 | 2 | test_file: 13-config.yaml purpose: structured extractio |
| 11 | FAIL | NO | n/a | extractive evidence_synth | 11 | 2 | [refused: citation_density_low] |
| 12 | FAIL | n/a | 12-notes.md | extractive evidence_synth | 11 | 3 | # DuckDocs Test File - Markdown This tests plain text/m |
| 13 | FAIL | n/a | 12-notes.md | extractive evidence_synth | 11 | 3 | # DuckDocs Test File - Markdown This tests plain text/m |

**Each run aggregate:** 3 PASS, 2 PARTIAL, 8 FAIL; 0 passing answers had a
wrong or missing citation. The source column reports every citation returned
by the API, including a mismatched neighboring source; the scorecard's
measurement-only expected-source check therefore correctly marks Q2 as FAIL.

### Top-five retrieval measurement

Scores below are the post-fusion scores logged at DEBUG, showing document name
and score only. Duplicate names represent distinct evidence units/pages.

| Q | Top five documents and scores |
|---:|---|
| 1 | 12-notes.md 1.000; 02-scanned-ocr.pdf 1.000; 11-page.html 1.000; 08-presentation.pptx 1.000; 03-scanned-multipage.pdf 1.000 |
| 2 | 02-scanned-ocr.pdf 1.000; 03-scanned-multipage.pdf 1.000; 03-scanned-multipage.pdf 1.000; 03-scanned-multipage.pdf 1.000; 04-image-text.png 1.000 |
| 3 | Kyoto_Japan_itinerary.pdf 1.000; Kyoto_Japan_itinerary.pdf 0.984; Kyoto_Japan_itinerary.pdf 0.968; Kyoto_Japan_itinerary.pdf 0.953; Kyoto_Japan_itinerary.pdf 0.938 |
| 4 | 03-scanned-multipage.pdf 1.000; 03-scanned-multipage.pdf 1.000; 03-scanned-multipage.pdf 1.000; 02-scanned-ocr.pdf 1.000; 08-presentation.pptx 1.000 |
| 5 | 08-presentation.pptx 1.000; 08-presentation.pptx 1.000; 03-scanned-multipage.pdf 1.000; 03-scanned-multipage.pdf 1.000; 03-scanned-multipage.pdf 1.000 |
| 6 | 06-document.docx 1.000; 06-document.docx 1.000; 03-scanned-multipage.pdf 0.968; 03-scanned-multipage.pdf 0.953; 03-scanned-multipage.pdf 0.938 |
| 7 | 07-spreadsheet.xlsx 1.000; 06-document.docx 0.984; 13-config.yaml 0.968; 07-spreadsheet.xlsx 0.953; 14-data.xml 0.938 |
| 8 | 07-spreadsheet.xlsx 1.000; 07-spreadsheet.xlsx 1.000; 09-data.csv 1.000; 02-scanned-ocr.pdf 0.953; Kyoto_Japan_itinerary.pdf 0.938 |
| 9 | 09-data.csv 1.000; 12-notes.md 0.984; 13-config.yaml 0.968; 07-spreadsheet.xlsx 0.953; 02-scanned-ocr.pdf 0.938 |
| 10 | 13-config.yaml 1.000; 12-notes.md 1.000; 11-page.html 1.000; 03-scanned-multipage.pdf 1.000; 03-scanned-multipage.pdf 1.000 |
| 11 | 14-data.xml 1.000; 06-document.docx 1.000; 07-spreadsheet.xlsx 0.984; 13-config.yaml 0.968; 12-notes.md 0.938 |
| 12 | Kyoto_Japan_itinerary.pdf 1.000; Kyoto_Japan_itinerary.pdf 0.984; 12-notes.md 0.968; Kyoto_Japan_itinerary.pdf 0.953; Kyoto_Japan_itinerary.pdf 0.938 |
| 13 | 14-data.xml 1.000; 12-notes.md 0.984; 09-data.csv 0.968; 13-config.yaml 0.953; Kyoto_Japan_itinerary.pdf 0.938 |

The remaining Q1/Q11 citation-density refusals and Q5 short answer are
grounding/output-quality issues for later phases; this phase did not weaken
the fail-closed gate.

## Phase 2b structured-answer diagnosis and result

The throwaway diagnostic ran the same retrieval, prompt construction, and Ollama
generation settings as the application. Raw responses were kept only in the
backend container at `/tmp/phase2b_raw.json` and were not committed.

### Initial failure reasons

| Reason | Count |
|---|---:|
| Truncated at `num_predict` (`done_reason=length`, `eval_count=128`) | 11 |
| Unknown evidence ID (`done_reason=stop`) | 2 |
| Invalid JSON | 0 |
| Quote not found | 0 |
| Accepted | 0 |

The five junk classes were covered by failing regression tests before the
change. The first-person/meta class could pass the old gate because the old
citation-density logic only checked factual-looking sentences; a response
containing only a persona/meta sentence had zero factual claims and therefore
was not rejected. The gate is now fail-closed and requires a verified answer
and at least one non-empty cited passage.

### Controlled experiments

| Contract | `num_predict` | JSON | Passages | Accepted | Seconds/question |
|---|---:|---|---:|---:|---:|
| Claims plus copied quotes | 128 | on | 6 | 0/13 | 5.56 |
| Claims plus copied quotes | 128 | off | 6 | 0/13 | 5.18 |
| Claims plus copied quotes | 256 | on | 6 | 0/13 | 9.75 |
| Claims plus copied quotes | 384 | on | 6 | 0/13 | 11.64 |
| Claims plus copied quotes, numeric labels | 256 | on | 6 | 0/13 | 12.18 |
| Claims plus copied quotes | 256 | on | 3 | 1/13 | 6.99 |
| Short answer plus passage numbers | 128 | on | 6 | 6/13 | 5.34 |
| Short answer plus passage numbers | 256 | on | 6 | 6/13 | 2.33 |

The adopted contract is the short answer plus numeric passage labels, with the
existing 128-token cap retained to minimize latency. The displayed citation
quote remains selected by the application from stored evidence; model output
does not supply display text. Corrective retries are configurable through
`DUCKDOCS_ASK_RETRIES` and default to zero.

### Rebuilt-stack scorecard runs

| # | Run 1 | Seconds | Run 2 | Seconds |
|---:|---|---:|---|---:|
| 1 | FAIL | 23 | FAIL | 3 |
| 2 | FAIL | 6 | FAIL | 3 |
| 3 | PASS | 13 | PASS | 3 |
| 4 | PASS | 5 | PASS | 3 |
| 5 | PASS | 5 | PASS | 3 |
| 6 | FAIL | 5 | FAIL | 2 |
| 7 | PASS | 5 | PASS | 2 |
| 8 | FAIL | 5 | FAIL | 2 |
| 9 | PARTIAL | 5 | PARTIAL | 2 |
| 10 | FAIL | 4 | FAIL | 2 |
| 11 | PARTIAL | 4 | PARTIAL | 2 |
| 12 | FAIL | 5 | FAIL | 2 |
| 13 | FAIL | 5 | FAIL | 3 |

Both runs: **4 PASS, 2 PARTIAL, 7 FAIL**, with zero passing answers having a
wrong or missing citation. The remaining failures are retrieval/source and
structured-data quality issues reserved for later phases.

### Threading and ingestion observations

The SQL repository does not share a SQLAlchemy `Session` across
`asyncio.to_thread` calls: each repository operation creates and closes its own
`SessionLocal` context. The in-memory repository uses process-local dictionaries
and has no request-scoped session. The vector store shares its Chroma client
object, but each query is a synchronous client operation with no session state
stored on the request; this was not changed in Phase 2b. Summary generation
still competes for the same Ollama model during ingestion; moving summaries
behind indexing remains a follow-up.

### Test result

Focused Phase 2b validation: **23 passed**. The full locally configured suite
reported **136 passed, 3 skipped, 2 failed**; both failures were pre-existing
OCR/environment-sensitive assertions (RapidOCR spacing and standalone image
keyword retrieval), not caused by the structured-answer changes.

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
