# Phase 6: DOCX page awareness

Baseline: `scorecard_phase5b-verify.json`, HEAD `199b551` (12 PASS / 0 PARTIAL / 1 FAIL).

DOCX body paragraphs and table-cell paragraphs are read in document order. Page
numbers are physical, one-based positions derived from explicit page breaks,
page-break-before (including inherited paragraph styles), section starts, and
stored rendered page-break markers. A rendered marker immediately following a
hard boundary confirms that boundary instead of creating an extra page. Empty
pages retain their physical position. Continuous sections do not create a page;
odd/even section starts retain intervening blank pages. Referenced running
headers/footers belong to their section's pages and do not enter body counts.

DOCX is marked `structural`: this parser does not perform Word layout or infer
unrecorded automatic wrapping. Rendered markers describe the last saved layout
and can be stale after edits in tools that do not refresh them. Page numbers are
physical positions, not restarted/custom page labels in a footer.

Evidence is split at body paragraph, table-cell paragraph and page boundaries.
Long paragraphs retain their ordinal across bounded overlapping chunk windows.
Table cells retain their table/row/cell location in the existing section field.
The existing `page` field needs no schema change; migration `0006` adds nullable
`paragraph_number` so body ordinals survive repository restarts. Legacy rows
remain intact with an unknown ordinal until re-ingestion.

Re-ingest existing DOCX files using their document retry action after rebuilding
and applying migrations. This replaces their derived evidence/vector records
from the preserved original upload; do not upload duplicate library documents.
Other formats do not require re-ingestion for this phase.

One page-reference parser handles numeric/cardinal/ordinal page and slide forms,
including compound ordinals, `last`/`final`, and `after the [ordinal] page break`.
Unqualified `after the page break` means the page beginning at the first boundary
(physical page 2); the third boundary begins page 4. An explicit destination page
takes precedence. Conflicting explicit page numbers select nothing.

Page selectors constrain each document before vector top-k, keyword fusion and
deduplication, and the same parser checks citations in the grounding gate. The
last page comes from the document's full page count, including a blank last page,
not the last retrieved chunk. Slide selectors require PPTX; page selectors also
work for PDF, DOCX and paginated images. Existing format and document scope rules
still apply. Identical text on different pages retains separate provenance.

Citations include an additive `page` field populated from stored evidence, never
model text. The UI normally resolves the evidence record and displays its page;
if that lookup fails, it preserves the citation's page. A legacy citation without
either location displays `Page unavailable` instead of inventing page 1.

The existing label-value regression now supplies all parsed DOCX paragraphs to
retrieval. Its old assumption that the entire document occupied `chunks[0]` no
longer represented ingestion; the expected label value and exact quote are unchanged.

Synthetic tests build their own documents with `python-docx==1.2.0`, a small dev
dependency. On each rebuilt test container, install it before the standard test
block: `docker compose exec -u root backend pip install -q python-docx==1.2.0`.
Then copy `backend/tests` and run container pytest as in the handoff preamble.

OOXML behavior references:
- https://python-docx.readthedocs.io/en/latest/dev/analysis/features/text/breaks.html
- https://python-docx.readthedocs.io/en/latest/dev/analysis/features/sections.html
