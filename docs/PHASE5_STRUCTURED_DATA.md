# Structured evidence

Migration 0004 adds nullable table row metadata and the parsed file type. Existing
evidence is preserved. **Re-ingest existing CSV and XLSX documents using Retry** to
populate row evidence and replace their old vectors. Keep uploaded originals and
back up the database/evidence/vector state first; do not delete the data directory.

The first nonempty row is the header. Each nonempty physical row has its own
evidence unit, including a header unit. Headers and cells retain column positions,
blank cells and duplicate headings. Worksheet name, physical row number and full
data-row count are stored alongside the cells. A capped/incomplete table must not
be used for a calculation. Sheets are independent tables. Formula cells use cached
workbook values; uncached or nonnumeric inputs must not be treated as zero.

Plans are selected from column names, operation words and equality/comparison
operators. Supported operations are lookup/filter, count, sum, average, min and
max. Filters on different columns are combined with AND; multiple mentioned text
values on one column use OR. Numeric inputs use Decimal, with validated comma
thousands separators, currency symbols/codes, negatives and percentages (displayed
in percentage points). Ambiguous columns, incomplete tables, nonnumeric cells and
incompatible units are refused. There is no model planner or executable code path.

Structured Q&A reads the complete stored table, not a retrieval top-k sample. A
second pass reads cells again and independently recomputes the selected inputs and
result. Any mismatch refuses the answer. Calculations show their inputs and only
cite relevant cell quotes, with sheet/row/column coordinates. Lookups return only
requested columns (plus an identity column for "who/which" questions). The API adds
optional citation coordinates and a human-readable refusal_detail; the Ask UI
shows that explanation. Explicit Excel requests cannot use CSV; an ambiguous table
requires a file/sheet name rather than choosing arbitrary evidence.

Migration 0005 adds nullable key_value metadata. **Retry existing JSON, YAML/YML
and XML documents** to populate key-path evidence and replace old text vectors.
JSON/YAML leaves use JSONPath-style paths; XML text/attributes use element paths
with repeated-sibling indices. Every selected value is checked against the stored
path quote. Ambiguous leaves require a full path. Collection questions select
only the named collection's values, and unrelated XML attributes are excluded.
Duplicate keys, unsafe YAML tags, cyclic aliases and XML entity declarations are
rejected. PyYAML 6.0.3 is now directly pinned (it was already a small transitive
dependency); it does not download models or make network calls.
An explicit full path takes precedence over shared leaf names, including XML
element indices and attributes on repeated siblings.

Binary content signatures and OOXML archive members determine PDF/image/Office
formats before ingestion. An XLSX named .csv retains its original name/bytes but
is stored and parsed as XLSX, with the Excel MIME type and cell anchors. Retry also
detects content again, repairing old format metadata. Corrupt/ambiguous ZIPs,
legacy binary Office, unknown binary content and text masquerading as a binary
format receive an actionable upload/retry error. YAML/CSV/plain text have no
unique magic signature, so validated text still uses its supported extension.

Two old test inputs were corrected: prose renamed JSON/XML is invalid structured
syntax; a fake PK-prefixed string is not a DOCX archive. Both tests now use valid
synthetic content while preserving their original format/download assertions.

Re-ingestion replaces evidence IDs transactionally. SQL deleted identities are
flushed before inserting their replacements; otherwise reused IDs can disappear
at commit. Re-ingestion tests cover extending/shrinking a table and restarting the
repository. Structured evidence from a failed/processing document is excluded.
Explicit YAML/JSON/XML hints take precedence over the generic word "config".
Filter cells are included in exact citation quotes alongside the requested value,
so a citation establishes which entity/month/row supplied it.
Structured lookups retain the existing numeric/date answer-type check. It examines
selected cell/key values, excluding row numbers and path indices, and refuses
missing amounts with answer_type_missing. Synthetic tests cover both refusals and
valid currency values in CSV, JSON, YAML and XML.

Phase 5 validation uses synthetic documents and container pytest only. The full
recovery suite passed 263 tests. The recovery scorecard against
scorecard_phase3b-terminal1-verify.json improved from 8 PASS / 3 PARTIAL / 2 FAIL to
12 PASS / 0 PARTIAL / 1 FAIL, with no regressions or passing wrong/missing citations.
The final committed HEAD is rebuilt and measured separately; complete terminal
output and the baseline-column table are in output/phase5 (workspace root).
The existing DOCX page-answer failure is retained for a later phase; Phase 6 was
not started. The MIN_SUPPORT default remains 0.1. Held-out files are not used.
