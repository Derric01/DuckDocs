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
