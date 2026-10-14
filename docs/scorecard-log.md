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

## Phase 5 — structured data and content detection (13 October 2026)

Baseline: `scorecard_phase3b-terminal1-verify.json`, verified Phase 3B HEAD
`1547993` (8 PASS / 3 PARTIAL / 2 FAIL). Recovery measurement after all code changes:

```text
Q   Baseline  Phase 5
1   PASS      PASS
2   PASS      PASS
3   PASS      PASS
4   PASS      PASS
5   PASS      PASS
6   FAIL      FAIL
7   PASS      PASS
8   FAIL      PASS
9   PARTIAL   PASS
10  PARTIAL   PASS
11  PARTIAL   PASS
12  PASS      PASS
13  PASS      PASS
Regressions versus baseline: none
PASS 12 / PARTIAL 0 / FAIL 1; passing wrong/missing citations: 0
Container pytest: 263 passed (7 existing dependency/config warnings)
```

The first Phase 5 scorecard regressed Q9/Q10/Q11. Verification stopped and the
failures were reported. SQL re-ingestion reused deleted identities, removing
headers/first paths at commit; deleted rows now flush before replacement inserts.
The generic word "config" also broadened explicit YAML to JSON/XML; explicit
format hints now stay strict. Synthetic re-ingestion and mixed-format tests cover
both fixes. Independent completeness checks were retained.

Migrations 0004/0005 applied to the real PostgreSQL repository. Five affected
documents were retried after a local pre-change evidence/vector backup; every
original upload SHA-256 hash stayed unchanged. The library has 15 documents,
53 evidence units and the same 53 vector IDs, including three complete tables
and three complete key-path documents. MIN_SUPPORT remains 0.1.

An additional synthetic compatibility check caught structured lookups bypassing
the existing numeric answer-type guard. CSV/JSON/YAML/XML now verify selected
values (excluding row/path numbers); all four refusal/valid-currency tests pass.

Final committed-HEAD verification, all commands, per-question provider/chunks/
seconds/answer starts, baseline comparison and changed files are recorded in
`output/phase5/Phase5_Report.txt` (workspace root). Q6's pre-existing DOCX/page
limitation remains. Phase 6 was not started; no held-out files were accessed.

## Phase 5b — structured query selection follow-up (13 October 2026)

Baseline: measured Phase 5 HEAD `a8f8543`, `scorecard_phase5-verify.json`
(12 PASS / 0 PARTIAL / 1 FAIL). The operator's independent results rejected Phase
5 acceptance despite its public scorecard; the follow-up targets reported failure
classes without inspecting private questions or expected answers.

Changes: unambiguous schema aliases/natural person counts; source/sheet selectors
and schema feasibility instead of row-frequency scores; inclusive month ranges,
literal entity binding, comparison aliases and question-plan verification before
independent arithmetic checks. Synthetic tests retain refusals for ambiguous or
unsupported plans, missing entities, and money/quantity alias collisions.

The preliminary full container suite passed 297 tests. Its rebuilt public
scorecard remained 12/0/1 with no regressions or passing wrong/missing citations.
Six final schema-boundary/routing cases passed in the 108-test focused suite:
missing measures for identified table entities refuse deterministically, while
calendar words alone do not redirect ordinary document questions. Final
committed-HEAD tests, all 13 baseline-column rows, source/provider/timing/answer
starts, plan traces and changed files are in
`output/phase5b/Phase5b_Report.txt` (workspace root). The public result is expected
to be neutral: these generic wording/selection failures are not covered by its
13 questions. Private acceptance still requires the operator's independent rerun.

No migration, re-ingestion, new dependency, default model/threshold change, push
or Phase 6 work is included.

## Phase 6 — DOCX page awareness (14 October 2026)

Baseline: `scorecard_phase5b-verify.json` at `199b551` (12 PASS / 0 PARTIAL /
1 FAIL). The scorecard questions and grading patterns are unchanged, including
Q6's existing second-page paragraph wording.

DOCX parsing preserves explicit, paragraph-property, section and saved rendered
boundaries, with physical page numbers and page-local body paragraph ordinals.
The shared query parser constrains page/slide retrieval and citation validation.
Located paragraph reads return verified stored text; citations preserve its page
through the API and UI. Migration `0006` requires existing DOCX files to be retried
from their original uploads. Details and counting rules are in
`docs/PHASE6_DOCX_PAGES.md`.

Synthetic Office packages cover the boundary types, page-spanning table cells,
blank pages, inherited properties, headers/footers, repository persistence,
Alembic upgrades, paragraph counting and retry of stale page counts. The final
focused parser/citation run passed 17 tests; citation/API client UI tests passed
35 tests. Ruff passed the new parser modules and migration; strict mypy passed
the two new parser modules. This is not a claim of a repository-wide static check.

Final committed-HEAD container pytest and rebuilt scorecard measurements, all
13 baseline-column rows, regressions, providers, sources, timing, answer starts,
model acceptance count, runtime metadata checks and changed files are recorded in
`output/phase6/Phase6_Report.txt` at the workspace root, with adjacent raw logs.
The operator's private acceptance check remains independent; its files were not
read. Default models and `DUCKDOCS_MIN_SUPPORT` remain unchanged. Phase 7 is outside
this work.

### Phase 3 final

The support gate uses `DUCKDOCS_MIN_SUPPORT=0.1`. It is applied when the
library has at least two documents, because IDF support is not meaningful in a
single-document corpus. The highest refusal support score was 0.0738, giving
0.0262 margin below the threshold; the lowest answerable score was 0.1358,
giving 0.0358 margin above it. Numeric/date questions also require a matching
number, currency amount, or date, and entity/property questions use
rarity-weighted attribute support. Compact labels such as `Testmarker` are
matched against spaced query terms.

Container validation: `169 passed, 7 warnings in 35.13s`.

Final rebuilt scorecard (`phase3-final3`), compared with
`scorecard_phase4f-verify.json`: 8 PASS, 3 PARTIAL, 2 FAIL; no regressions.
The two remaining failures are Q6 (citation-density validation) and Q8
(claim-not-in-evidence); these are not refusal-calibration regressions.

## Phase 4e validation

The requested container bisect was run with a rebuild and a focused scorecard
check at each selected commit. The first reported bad commit for Q2, Q5, and
Q11 was `dbbbf6e` (`fix: prevent ready documents without evidence`). The
combined predicate was intentionally conservative: a commit was bad if any
of the three expected outcomes was absent. This identifies the first shared
regression boundary; it does not prove that the evidence-persistence change
itself caused all three answer regressions.

The final container test run after the ordinal-page and extraction-ranking
changes was `158 passed, 7 warnings`. The rebuilt scorecard run
(`phase4e-final2`) remained `5 PASS, 3 PARTIAL, 5 FAIL`; the baseline comparison
reported `Q2: PASS -> FAIL`. Q1, Q5, and Q11 were not regressions relative to
`00e4714`.

| Q | Result | Cited | Source files | Provider | Chunks | Seconds | Reason | Answer start |
|---:|---|---|---|---|---:|---:|---|---|
| 1 | PASS | yes | 01-native-text.pdf | extractive evidence_synth | 5 | 7 |  | Test marker: NATIVE-PDF-7f3a2b. |
| 2 | FAIL | NO | 03-scanned-multipage.pdf | extractive evidence_synth | 4 | 3 |  | Page marker:SCAN-PAGE-3-b82e |
| 3 | PASS | yes | Kyoto_Japan_itinerary.pdf | ollama llama3.2:1b | 12 | 3 |  | The annual average high temperature... |
| 4 | PASS | yes | 03-scanned-multipage.pdf | extractive evidence_synth | 3 | 7 |  | Page marker:SCAN-PAGE-2-b82e |
| 5 | PASS | yes | 08-presentation.pptx | extractive evidence_synth | 3 | 2 |  | Slide 3 Slide 3: Final marker |
| 6 | FAIL | NO | 06-document.docx | extractive evidence_synth | 2 | 2 |  | Second paragraph with a page break... |
| 7 | PASS | yes | 07-spreadsheet.xlsx | extractive evidence_synth | 12 | 3 |  | Sheet: Inventory |
| 8 | FAIL | yes | 07-spreadsheet.xlsx | extractive evidence_synth | 3 | 2 |  | Sheet: Sales |
| 9 | PARTIAL | yes | 09-data.csv | extractive evidence_synth | 12 | 3 |  | id \| name \| department |
| 10 | PARTIAL | yes | 13-config.yaml | extractive evidence_synth | 3 | 3 |  | test_file: 13-config.yaml |
| 11 | PARTIAL | yes | 14-data.xml | extractive evidence_synth | 1 | 2 |  | XML-MARKER-6f3c |
| 12 | FAIL | n/a | 12-notes.md | extractive evidence_synth | 12 | 3 |  | DuckDocs Test File |
| 13 | FAIL | n/a | 12-notes.md | extractive evidence_synth | 12 | 3 |  | DuckDocs Test File |

Top-5 signal maxima were: Q1 `0.7435/1.0000`, Q2 `0.8014/0.5144`,
Q3 `0.8328/0.8530`, Q4 `0.7325/0.4375`, Q5 `0.6816/0.3258`,
Q6 `0.6486/0.4560`, Q7 `0.6279/0.2565`, Q8 `0.8089/0.2405`,
Q9 `0.7435/0.2036`, Q10 `0.7708/0.4208`, Q11 `0.6297/0.1358`,
Q12 `0.6269/0.3238`, and Q13 `0.5936/0.0738` (cosine/lexical).

The Q2 gate trace is: the extractive provider produced a page-3 marker from
`03-scanned-multipage.pdf`; citation binding rejected it because the expected
source was absent. Q5 and Q11 were accepted by the same rebuilt run. The
ordinal-page and higher-ranked-evidence fixes are committed after this
measurement and require another rebuild/scorecard run before acceptance.

## Phase 4f validation

Plain-text bisect result from the scripted rebuild-and-scorecard run:

```text
Q2 first bad commit: dbbbf6ece5294f2d3a984436648aec0dd000b0a7
Q5 first bad commit: dbbbf6ece5294f2d3a984436648aec0dd000b0a7
Q11 first bad commit: dbbbf6ece5294f2d3a984436648aec0dd000b0a7
```

This is the first shared bad boundary for the combined expected-outcome
predicate, not proof that the evidence-persistence change independently caused
each regression.

The final rebuilt HEAD (`phase4f-final3`) container suite was:

```text
162 passed, 7 warnings in 32.32s
```

The final scorecard was `6 PASS, 3 PARTIAL, 4 FAIL`, with no regressions versus
`scorecard_phase4c-reingested.json`.

Q2 decision trace:

```text
Model answer produced: yes.
Model provider: Ollama llama3.2:1b.
Model rejection reason: empty_evidence.
Fallback provider: extractive evidence_synth.
Fallback source: 02-scanned-ocr.pdf.
Fallback answer: Testmarker:SCAN-PDF-9d1c4e.
```

Before Phase 4f, Q2's fused scores tied at `1.0`, so fallback context ordering
could select `03-scanned-multipage.pdf` despite lower absolute signals. The
absolute tie-break now uses raw cosine plus lexical coverage and a generic
document-name token boost. For Q2, `02-scanned-ocr.pdf` ranks ahead with
cosine `0.8014` / lexical `0.4876`, versus
`03-scanned-multipage.pdf` cosine `0.7429` / lexical `0.5144`.

The scorecard now prints a `Model rejected` column sourced from the API
diagnostic field. Final model-rejection reasons included Q2 `empty_evidence`,
Q4 `no_evidence`, Q5 `content_not_informative`, and Q7 `empty_evidence`.

The JSON evidence-count check was also performed against the running stack:

```text
10-data.json: 1 evidence unit
```

The current JSON scorecard question was not refused; it returned a grounded
partial answer from `13-config.yaml`. The synthetic JSON key/value regression
passes. A `no_evidence` response at the retrieval stage would require zero
retrieved candidates; the JSON document itself is not empty, so its evidence
count is not the cause.

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

## Phase 4b follow-up

Phase 4b addressed the regressions identified against the Phase 2b baseline:

- Model answers whose content adds no information beyond the question are now
  rejected and sent through the extractive fallback. This fixes the grounded
  but useless `Slide 3.` response for Q5.
- Structured evidence answers may pass density validation when the cited
  evidence is XML, YAML, JSON, or CSV and the answer contains structured
  content. The prior Phase 4 refusal happened because the extractive XML
  response was treated as a sequence of factual text without sufficient
  sentence-level citation coverage, so `citation_density_low` discarded it.
- Displayed citations now require distinctive answer values such as marker
  tokens to occur in the selected stored snippet. If the value is absent, the
  citation is dropped and the response fails closed; derived totals remain
  valid when their source rows support the calculation.
- Scorecard source grading now returns PARTIAL when the expected source is
  cited together with unrelated sources, and FAIL only when the expected
  source is absent.

### Phase 4b scorecard runs

The backend image was rebuilt before each run. The results were identical:

| Q | Result | Cited | Sources | Provider | Chunks | Secs | Answer start | Phase 2b comparison |
|---:|---|---|---|---|---:|---:|---|---|
| 1 | FAIL | NO | n/a | extractive evidence_synth | 12 | 5 / 3 | [refused: citation_density_low] | FAIL |
| 2 | FAIL | NO | n/a | ollama llama3.2:1b | 12 | 6 / 3 | [refused: no_verified_claims] | FAIL |
| 3 | PASS | yes | Kyoto_Japan_itinerary.pdf | ollama llama3.2:1b | 12 | 12 / 3 | The annual average high temperature in Kyoto is 21.0°C | PASS |
| 4 | PASS | yes | 03-scanned-multipage.pdf | extractive evidence_synth | 12 | 5 / 3 | Page marker:SCAN-PAGE-2-b82e | PASS |
| 5 | PASS | yes | 08-presentation.pptx | extractive evidence_synth | 11 | 4 / 2 | Slide 3 Slide 3: Final marker Test marker: PPTX-SLIDE3- | **REGRESSION FIXED: FAIL -> PASS** |
| 6 | FAIL | NO | 06-document.docx | extractive evidence_synth | 11 | 5 / 2 | DuckDocs Test File - Word Document This DOCX tests para | FAIL |
| 7 | PASS | yes | 07-spreadsheet.xlsx | extractive evidence_synth | 12 | 5 / 3 | Sheet: Inventory SKU \| Item \| Stock A-100 \| Widget A \| | PASS |
| 8 | FAIL | yes | 07-spreadsheet.xlsx | extractive evidence_synth | 12 | 5 / 2 | Sheet: Sales Month \| Revenue \| Units Jan \| 12000 \| 340 | FAIL |
| 9 | PARTIAL | yes | 09-data.csv | extractive evidence_synth | 11 | 5 / 3 | id \| name \| department \| salary 1 \| Asha Rao \| Engineer | PARTIAL |
| 10 | PARTIAL | yes | 13-config.yaml | extractive evidence_synth | 12 | 4 / 3 | test_file: 13-config.yaml purpose: structured extractio | PARTIAL |
| 11 | PARTIAL | yes | 14-data.xml | extractive evidence_synth | 11 | 2 / 2 | <?xml version="1.0"?> <root> <marker>XML-MARKER-6f3c</m | **REGRESSION FIXED: FAIL/refused -> PARTIAL** |
| 12 | FAIL | n/a | 12-notes.md | extractive evidence_synth | 11 | 5 / 3 | # DuckDocs Test File - Markdown This tests plain text/m | FAIL |
| 13 | FAIL | n/a | 12-notes.md | extractive evidence_synth | 11 | 5 / 3 | # DuckDocs Test File - Markdown This tests plain text/m | FAIL |

**Each Phase 4b run:** 4 PASS, 3 PARTIAL, 6 FAIL; zero passing answers had
wrong or missing citations. Compared with Phase 2b's 4 PASS, 3 PARTIAL, 6
FAIL measurement, Q5 and Q11 are no longer regressions. Q2 now correctly
fails closed because its answer's marker was not present in the selected
stored quote.

### Q1 and refusal-threshold measurements

For Q1, `01-native-text.pdf` was **not** among the top five retrieved
passages. The post-fusion top five were:

`12-notes.md 1.000; 02-scanned-ocr.pdf 1.000; 11-page.html 1.000;
08-presentation.pptx 1.000; 03-scanned-multipage.pdf 1.000`.

The native PDF was therefore missed during retrieval, rather than rejected by
the grounding gate. This is a retrieval-ranking issue, not a citation
verification failure.

Q12 and Q13 remained non-answerable but retrieved neighboring evidence:

| Question | Top-five documents and scores |
|---:|---|
| 12 | Kyoto_Japan_itinerary.pdf 1.000; Kyoto_Japan_itinerary.pdf 0.984; 12-notes.md 0.968; Kyoto_Japan_itinerary.pdf 0.953; Kyoto_Japan_itinerary.pdf 0.938 |
| 13 | 14-data.xml 1.000; 12-notes.md 0.984; 09-data.csv 0.968; 13-config.yaml 0.953; Kyoto_Japan_itinerary.pdf 0.938 |

These scores overlap the answerable questions substantially, so a single
retrieval threshold cannot separate the refusal cases. Refusal calibration
and IDF-weighted lexical support remain Phase 3 work.

### Test environments

The mandated backend-container run passed: **146 passed, 7 warnings** using
Python 3.12 after rebuilding the image and copying `backend/tests` into the
container. The earlier host-only failures are not the Phase 4b headline:
the host has `rapidocr-onnxruntime 1.2.3` and `chromadb 1.5.9`, while the
backend project pins `rapidocr-onnxruntime==1.4.4` and
`chromadb==0.5.23`. The RapidOCR spacing and image keyword failures were
therefore environment-specific.

## Phase 4c retrieval signals and citation re-selection

Phase 4c applies document-format, native/scanned, page, and slide hints before
vector and keyword top-k truncation. Native-text PDF means a PDF evidence unit
whose metadata is not `ocr_dependent`; scanned means `ocr_dependent`. Keyword
coverage is IDF-weighted across unique library documents. Retrieved chunks now
carry raw vector cosine and lexical coverage alongside the fused rank score.
The displayed quote is re-selected from the cited passage when a distinctive
answer value is present there but was omitted from the first selected span.

The backend image was rebuilt before each run. Both runs were identical:

| Q | Result | Cited | Sources | Provider | Chunks | Secs 1 / 2 | Answer start | dbc914c |
|---:|---|---|---|---|---:|---:|---|---|
| 1 | FAIL | NO | n/a | extractive evidence_synth | 4 | 23 / 2 | [refused: no_verified_claims] | FAIL |
| 2 | PASS | yes | 02-scanned-ocr.pdf | ollama llama3.2:1b | 6 | 6 / 3 | The test marker in the scanned OCR PDF is SCAN-PDF-9d1c | FAIL |
| 3 | PASS | yes | Kyoto_Japan_itinerary.pdf | ollama llama3.2:1b | 12 | 12 / 3 | The annual average high temperature in Kyoto is 21.0°C | PASS |
| 4 | PASS | yes | 03-scanned-multipage.pdf | extractive evidence_synth | 3 | 8 / 6 | Page marker:SCAN-PAGE-2-b82e | PASS |
| 5 | PASS | yes | 08-presentation.pptx | extractive evidence_synth | 3 | 2 / 2 | Slide 3 Slide 3: Final marker Test marker: PPTX-SLIDE3- | PASS |
| 6 | FAIL | NO | 06-document.docx | extractive evidence_synth | 2 | 3 / 3 | DuckDocs Test File - Word Document This DOCX tests para | FAIL |
| 7 | PASS | yes | 07-spreadsheet.xlsx | extractive evidence_synth | 12 | 5 / 3 | Sheet: Inventory SKU \| Item \| Stock A-100 \| Widget A \| | PASS |
| 8 | FAIL | yes | 07-spreadsheet.xlsx | extractive evidence_synth | 3 | 3 / 2 | Sheet: Sales Month \| Revenue \| Units Jan \| 12000 \| 340 | FAIL |
| 9 | PARTIAL | yes | 09-data.csv | extractive evidence_synth | 12 | 5 / 3 | id \| name \| department \| salary 1 \| Asha Rao \| Engineer | PARTIAL |
| 10 | PARTIAL | yes | 13-config.yaml | extractive evidence_synth | 1 | 2 / 2 | test_file: 13-config.yaml purpose: structured extractio | FAIL |
| 11 | PARTIAL | yes | 14-data.xml | extractive evidence_synth | 1 | 3 / 2 | <?xml version="1.0"?> <root> <marker>XML-MARKER-6f3c</m | PARTIAL |
| 12 | FAIL | n/a | 12-notes.md | extractive evidence_synth | 12 | 5 / 3 | # DuckDocs Test File - Markdown This tests plain text/m | FAIL |
| 13 | FAIL | n/a | 12-notes.md | extractive evidence_synth | 12 | 5 / 3 | # DuckDocs Test File - Markdown This tests plain text/m | FAIL |

Each run: **5 PASS, 3 PARTIAL, 5 FAIL**, with zero passing answers carrying
wrong or missing citations. Against the verified `dbc914c` result of **4 PASS,
2 PARTIAL, 7 FAIL**, Q2 improved from FAIL to PASS and Q10 improved from FAIL
to PARTIAL; there were no regressions in Q5 or Q11 and no aggregate
regressions.

### Absolute retrieval signals

The scorecard columns `Cos` and `Lex` are the top-ranked chunk's raw cosine
and IDF-weighted lexical coverage. Values were identical in both runs:

| Q | Raw cosine | Lexical coverage |
|---:|---:|---:|
| 1 | 0.4898 | 0.0000 |
| 2 | 0.0000 | 0.4430 |
| 3 | 0.0000 | 0.8170 |
| 4 | 0.0000 | 0.4026 |
| 5 | 0.6816 | 0.0000 |
| 6 | 0.0000 | 0.4429 |
| 7 | 0.0000 | 0.2542 |
| 8 | 0.0000 | 0.2277 |

## Phase 4d indexing and evidence-selection result

Phase 4d now verifies persisted evidence before marking a document Ready,
exposes read-only evidence counts for scorecard preflight, computes both
absolute retrieval signals for every candidate, derives format hints from
library extensions plus synonyms, accepts grounded JSON key/value answers, and
keeps adjacent entity context in extractive citations. The backend image was
rebuilt before each run. The container test suite reported:
`155 passed, 7 warnings in 34.41s`.

Both scorecard runs produced **4 PASS, 2 PARTIAL, 7 FAIL**, with zero passing
answers carrying a wrong or missing citation. The per-question result was
identical; seconds varied slightly:

| Q | Result | Cited | Sources | Provider | Chunks | Secs 1 / 2 | Answer start | dbc914c | 3cd493b |
|---:|---|---|---|---|---:|---:|---|---|---|
| 1 | PASS | yes | 01-native-text.pdf | extractive evidence_synth | 5 | 9 / 7 | Test marker: NATIVE-PDF-7f3a2b. | FAIL | FAIL |
| 2 | FAIL | NO | n/a | extractive evidence_synth | 4 | 3 / 3 | [refused: no_verified_claims] | FAIL | FAIL |
| 3 | PASS | yes | Kyoto_Japan_itinerary.pdf | ollama llama3.2:1b | 12 | 3 / 3 | The annual average high temperature in Kyoto is 21.0°C | PASS | PASS |
| 4 | PASS | yes | 03-scanned-multipage.pdf | extractive evidence_synth | 3 | 7 / 7 | Page marker:SCAN-PAGE-2-b82e Use this file to test DUCK | PASS | PASS |
| 5 | FAIL | NO | n/a | extractive evidence_synth | 3 | 2 / 3 | [refused: no_verified_claims] | PASS | PASS |
| 6 | FAIL | NO | 06-document.docx | extractive evidence_synth | 2 | 3 / 2 | Second paragraph with a page break coming next. | FAIL | FAIL |
| 7 | PASS | yes | 07-spreadsheet.xlsx | extractive evidence_synth | 12 | 3 / 3 | Sheet: Inventory SKU \| Item \| Stock A-100 \| Widget A \| | PASS | PASS |
| 8 | FAIL | yes | 07-spreadsheet.xlsx | extractive evidence_synth | 3 | 4 / 2 | Sheet: Sales Month \| Revenue \| Units Jan \| 12000 \| 340 | FAIL | FAIL |
| 9 | PARTIAL | yes | 09-data.csv | extractive evidence_synth | 12 | 3 / 3 | id \| name \| department \| salary 1 \| Asha Rao \| Engineer | PARTIAL | PARTIAL |
| 10 | PARTIAL | yes | 13-config.yaml | extractive evidence_synth | 3 | 3 / 3 | test_file: 13-config.yaml purpose: structured extractio | FAIL | PARTIAL |
| 11 | FAIL | NO | n/a | extractive evidence_synth | 1 | 3 / 2 | [refused: no_verified_claims] | PARTIAL | PARTIAL |
| 12 | FAIL | n/a | 12-notes.md | extractive evidence_synth | 12 | 3 / 3 | # DuckDocs Test File - Markdown This tests plain text/m | FAIL | FAIL |
| 13 | FAIL | n/a | 12-notes.md | extractive evidence_synth | 12 | 3 / 3 | # DuckDocs Test File - Markdown This tests plain text/m | FAIL | FAIL |

### Phase 4d top-five candidates

Each entry is `document fused/raw-cosine/lexical-coverage`; maxima are over
the five displayed candidates. These are document names and numeric signals
only, with no passage text.

| Q | Top five candidates | Max cosine / lexical |
|---:|---|---:|
| 1 | 01-native-text.pdf 1.0/0.7435/1.0; Kyoto_Japan_itinerary.pdf 1.0/0.4898/0.1053; Kyoto_Japan_itinerary.pdf 1.0/0.4097/0.3186; Kyoto_Japan_itinerary.pdf 1.0/0.3784/0.3186; Kyoto_Japan_itinerary.pdf 1.0/0.359/0.3186 | 0.7435 / 1.0000 |
| 2 | 02-scanned-ocr.pdf 1.0/0.8014/0.4876; 03-scanned-multipage.pdf 1.0/0.7429/0.5144; 03-scanned-multipage.pdf 1.0/0.7359/0.5144; 03-scanned-multipage.pdf 1.0/0.7282/0.5144 | 0.8014 / 0.5144 |
| 3 | Kyoto_Japan_itinerary.pdf 1.0/0.8328/0.853; Kyoto_Japan_itinerary.pdf 0.9839/0.6199/0.2652; Kyoto_Japan_itinerary.pdf 0.9683/0.5964/0.2652; Kyoto_Japan_itinerary.pdf 0.9531/0.546/0.2652; Kyoto_Japan_itinerary.pdf 0.9385/0.5393/0.4122 | 0.8328 / 0.8530 |
| 4 | 03-scanned-multipage.pdf 1.0/0.7325/0.4375; 03-scanned-multipage.pdf 1.0/0.724/0.4375; 03-scanned-multipage.pdf 1.0/0.7183/0.4375 | 0.7325 / 0.4375 |
| 5 | 08-presentation.pptx 1.0/0.6816/0.3258; 08-presentation.pptx 1.0/0.5819/0.3258; 08-presentation.pptx 1.0/0.4922/0.3258 | 0.6816 / 0.3258 |
| 6 | 06-document.docx 1.0/0.6486/0.456; 06-document.docx 1.0/0.6039/0.2532 | 0.6486 / 0.4560 |
| 7 | 07-spreadsheet.xlsx 1.0/0.6279/0.2565; 06-document.docx 1.0/0.5951/0.2565; 13-config.yaml 0.9683/0.487/0.0; 07-spreadsheet.xlsx 0.9531/0.4815/0.1593; Kyoto_Japan_itinerary.pdf 0.9385/0.4641/0.0 | 0.6279 / 0.2565 |
| 8 | 07-spreadsheet.xlsx 1.0/0.8089/0.2405; 07-spreadsheet.xlsx 1.0/0.4779/0.0802; 09-data.csv 1.0/0.4706/0.0 | 0.8089 / 0.2405 |
| 9 | 09-data.csv 1.0/0.7435/0.1648; 12-notes.md 0.9839/0.4378/0.0; 11-page.html 0.9683/0.4166/0.0; 02-scanned-ocr.pdf 0.9531/0.4127/0.0; 01-native-text.pdf 0.9385/0.4064/0.2036 | 0.7435 / 0.2036 |
| 10 | 13-config.yaml 1.0/0.7708/0.4208; 14-data.xml 0.9839/0.5862/0.0184; 10-data.json 0.9683/0.5298/0.0517 | 0.7708 / 0.4208 |
| 11 | 14-data.xml 1.0/0.6297/0.1358 | 0.6297 / 0.1358 |
| 12 | 12-notes.md 1.0/0.6269/0.0702; 01-native-text.pdf 0.9839/0.6/0.3238; 11-page.html 0.9683/0.5968/0.0702; 04-image-text.png 0.9531/0.5956/0.0702; 08-presentation.pptx 0.9385/0.5925/0.0702 | 0.6269 / 0.3238 |
| 13 | 12-notes.md 1.0/0.5936/0.0738; 03-scanned-multipage.pdf 0.9839/0.5652/0.0738; 11-page.html 0.9683/0.5614/0.0738; 03-scanned-multipage.pdf 0.9531/0.5531/0.0738; 06-document.docx 0.9385/0.5425/0.0738 | 0.5936 / 0.0738 |

Q1 is now PASS because the re-ingested native PDF has persisted searchable
evidence. Q5 regressed from PASS to refusal and Q11 regressed from PARTIAL to
refusal relative to the earlier Phase 4b/4c behavior; both have the correct
source in the top candidates, so these are citation-selection/grounding
regressions rather than retrieval misses. Q12 and Q13 still cite unrelated
Markdown evidence and remain deferred to Phase 3.
| 9 | 0.0000 | 0.1555 |
| 10 | 0.7708 | 0.0000 |
| 11 | 0.6297 | 0.0000 |
| 12 | 0.6269 | 0.0000 |
| 13 | 0.5936 | 0.0000 |

Q12/Q13 have raw cosine values overlapping answerable questions, while their
lexical coverage is zero. This supports combining absolute signals rather than
selecting a single fused-score threshold; refusal calibration remains Phase 3.

Q1's candidate filter now restricts retrieval to non-OCR PDFs, but the
currently loaded library has no evidence units for `01-native-text.pdf`
despite the document being reported `ready`; its candidate set therefore
contains the other native-text PDF evidence. This data/index inconsistency is
why Q1 still has no citation and requires investigation before treating the
retrieval rule as fully validated.

### Container validation

The rebuilt backend container suite passed: **148 passed, 7 warnings**.

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
