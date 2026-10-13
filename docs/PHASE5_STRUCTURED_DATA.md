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
