# Phase 5b: structured query selection

Baseline: a8f8543 and scorecard_phase5-verify.json (12 PASS / 0 PARTIAL / 1 FAIL).
The operator reported failures in column mapping, table selection and computed
answers. These classes are reproduced with synthetic data; private questions,
expected answers and result files are not read or used.

Column binding first uses exact headers, then a bounded schema vocabulary for
pay/salary, quantity/stock, revenue, price, identity and department concepts.
Aliases only bind columns that actually exist. Multiple matching headers require
an exact header; unknown attributes remain refusals. Natural row/person counts
do not require the user to mention a column. No embedding/model guesses are used.
The first focused container check passed 44 tests, including seven new cases.

Table selection honors file/scope/format and sheet locators, then checks whether
each table can bind the requested schema fields and entity filters. It does not
rank by repeated cell text or row count. Sheet/file references are removed from
the data query, so a sheet title cannot accidentally filter a cell with the same
text. Generic spreadsheet requests retain the XLSX preference among supporting
tables. Unknown named sheets and genuinely equivalent tables are refused.
Diagnostics expose the selected plan and each candidate's mapping outcome through
the existing optional diagnostic field. Five new synthetic workbook cases cover
sheet order, duplicate text, named-sheet quantities and preserved ambiguity;
the combined focused check passed 84 container tests.

These changes affect query planning only. No database or stored chunk metadata is
changed, so no migration or re-ingestion is required. Default models, privacy
settings, MIN_SUPPORT and existing grounding/completeness checks are retained.
