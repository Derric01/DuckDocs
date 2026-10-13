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
