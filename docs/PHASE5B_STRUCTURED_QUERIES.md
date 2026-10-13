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

Planning distinguishes a month list (OR over the listed months) from an inclusive
range, including ranges crossing December/January. Calendar filters bind only
month/period/date headers with compatible cells, not people whose names happen
to be months. Operation selection excludes entity names, column labels and filter
clauses; ambiguous multiple operations, unsupported grouping/OR comparisons and
unbound entities are refused. Comparison aliases bind a unique existing column.

Before arithmetic verification, the application checks that the executor retained
the original question plan and that the same plan binds against fresh stored
cells. Independent numeric recomputation and exact citation checks still follow.
Diagnostics expose operation, column, filters, candidate outcomes and plan_verified.
Eighteen new plan cases cover ranges/lists, averages, inflected comparisons,
literal cell identities, missing filters and a deliberately altered executor
plan whose arithmetic is otherwise correct. The combined focused check passed
102 container tests. The original failures were reproduced before fixing them.

Validation additionally prevents quantity aliases from binding unit prices/stock
valuations and pay aliases from binding grades, IDs or periods. Exact compound
headers remain usable. Person counts can use tables containing both ID and name
columns without choosing a projection. A literal person/product in an entity
column keeps an unmapped measure on the deterministic refusal path instead of
falling through to a model. Calendar words in month/date columns do not activate
that path for ordinary document questions. Six additional synthetic cases bring
the new case count to 36; the focused regression suite passed 108 tests.

The full preliminary container suite passed 297 tests before these last boundary
cases. The rebuilt preliminary scorecard was 12 PASS / 0 PARTIAL / 1 FAIL, exactly
matching the Phase 5 baseline, with zero passing wrong/missing citations. The
final committed HEAD is rebuilt and checked separately. Its complete commands,
outputs, per-question baseline comparison, source files, timing, plans and changed
files are recorded in output/phase5b/Phase5b_Report.txt at the workspace root.

These are verified failure classes, not claims that any unseen private question
has passed. The operator must rerun the private check independently before
accepting Phase 5b or proceeding to Phase 6.

These changes affect query planning only. No database or stored chunk metadata is
changed, so no migration or re-ingestion is required. Default models, privacy
settings, MIN_SUPPORT and existing grounding/completeness checks are retained.
