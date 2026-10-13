"""Rule-based plans over typed stored cells. No model output or code execution."""
from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal

from app.domain.models import Evidence

Operation = Literal["lookup", "count", "sum", "average", "min", "max"]
Comparator = Literal["eq", "ne", "gt", "ge", "lt", "le"]


class StructuredError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.diagnostic: dict[str, object] = {}


def normalized(value: str) -> str:
    value = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", value)
    words = re.findall(r"[\w]+", value.casefold().replace("_", " "))
    def singular(word: str) -> str:
        if word.endswith("ies"):
            return word[:-3] + "y"
        return word[:-1] if len(word) > 3 and word.endswith("s") and not word.endswith("ss") else word
    return " ".join(singular(word) for word in words)


def mentioned(value: str, query: str) -> bool:
    value = normalized(value)
    return bool(value and re.search(rf"(?<!\w){re.escape(value)}(?!\w)", normalized(query)))


# Aliases describe schema concepts, never document names or cell values.
_COLUMN_VOCABULARY = (
    (("salary", "wage", "pay", "earning", "compensation"),
     ("salary", "wage", "pay", "earn", "earning", "paid", "compensation")),
    (("unit", "quantity", "qty", "stock", "inventory"),
     ("unit", "quantity", "qty", "stock", "inventory", "available", "on hand", "in stock")),
    (("revenue", "receipt", "sales", "turnover"), ("revenue", "receipt", "sales", "turnover")),
    (("price", "cost", "fee", "charge"), ("price", "cost", "fee", "charge")),
    (("name", "person", "employee", "worker", "staff"), ("name", "person", "employee", "worker", "staff", "people")),
    (("department", "dept", "team", "division"), ("department", "dept", "team", "division")),
)


def _header_matches(labels: tuple[str, ...], header: str) -> bool:
    if not any(mentioned(label, header) for label in labels):
        return False
    if labels[0] in {"salary", "unit", "revenue", "price"}:
        categorical = ("id", "code", "name", "person", "type", "status", "band", "grade", "centre", "center")
        temporal = ("date", "month", "year", "period") if not mentioned("per", header) else ()
        if any(mentioned(word, header) for word in categorical + temporal):
            return False
        if labels[0] == "unit" and any(mentioned(word, header) for word in ("price", "cost", "fee", "charge", "value", "rate")):
            return False
    return True


def mapped_columns(headers: list[str], query: str, counting: bool = False) -> tuple[int, ...]:
    exact = {i for i, header in enumerate(headers) if mentioned(header, query)}
    selected = set(exact)
    for labels, words in _COLUMN_VOCABULARY:
        if not any(mentioned(word, query) for word in words):
            continue
        candidates = {i for i, header in enumerate(headers) if _header_matches(labels, header)}
        if not candidates:
            if any(any(mentioned(label, headers[i]) for label in labels) for i in exact):
                continue  # Explicit categorical/compound headers remain usable.
            raise StructuredError("column_unmapped", "The requested field is not represented by this table's headers.")
        explicit = candidates & exact
        candidates = explicit or candidates
        if len(candidates) > 1 and not explicit:
            if counting and labels[0] == "name":
                continue  # Counting people does not require choosing their ID/name projection.
            raise StructuredError("ambiguous_column", "Several columns match this wording. Name the exact header.")
        selected.update(candidates)
    return tuple(sorted(selected))


def _sheet_pattern(title: str) -> str:
    name = re.escape(title)
    return rf"(?:(?<!\w)[\"']?{name}[\"']?\s+(?:spreadsheet|worksheet|sheet)\b|\bsheet\s*(?::|named|called)?\s*[\"']?{name}[\"']?(?!\w))"


def table_query(query: str, unit: Evidence) -> str:
    query = re.sub(rf"(?:\b(?:in|on|from)\s+(?:the\s+)?)?(?<!\w){re.escape(unit.document_name)}(?!\w)", " ", query, flags=re.I)
    title = unit.table_row.sheet_name
    if title:
        query = re.sub(rf"\b(?:in|on|from)\s+(?:the\s+)?{_sheet_pattern(title)}", " ", query, flags=re.I)
        query = re.sub(_sheet_pattern(title), " ", query, flags=re.I)
        query = re.sub(rf"\b(?:in|on|from)\s+(?:the\s+)?{re.escape(title)}(?!\w)", " ", query, flags=re.I)
    return query


def plan_diagnostic(plan: Plan, headers: list[str]) -> dict[str, object]:
    return {"operation": plan.operation, "columns": [headers[i] for i in plan.columns],
            "filters": [{"column": headers[f.column], "operator": f.comparator, "values": list(f.values)} for f in plan.filters]}


def select_table(query: str, tables: dict[tuple[str, int], list[Evidence]], prefer_workbook: bool = False):
    """Use source selectors and schema feasibility; row frequency is not authority."""
    named_sheets = {key for key, units in tables.items() if units[0].table_row.sheet_name
                    and re.search(_sheet_pattern(units[0].table_row.sheet_name), query, re.I)}
    if named_sheets:
        tables = {key: units for key, units in tables.items() if key in named_sheets}
    elif re.search(r"\b(?:in|on|from)\s+(?:the\s+)?[\w -]+?\s+(?:worksheet|sheet)\b|\bsheet\s+(?:named|called)\s+", query, re.I):
        raise StructuredError("sheet_unmapped", "No stored table matches the named sheet. Check its exact name.")
    viable = {}
    errors = []
    traces = []
    for key, units in tables.items():
        effective = table_query(query, units[0])
        trace = {"document": units[0].document_name, "sheet": units[0].table_row.sheet_name}
        try:
            plan = plan_question(effective, units)
            viable[key] = (plan, effective)
            trace.update({"status": "mapped", **plan_diagnostic(plan, units[0].table_row.headers)})
        except StructuredError as error:
            errors.append(error)
            trace.update({"status": error.code})
        traces.append(trace)
    if not viable:
        error = next((e for e in errors if e.code != "column_unmapped"), errors[0]) if errors else StructuredError("column_unmapped", "No table column matches this question.")
        error.diagnostic = {"table_candidates": traces}
        raise error
    if prefer_workbook:
        workbooks = {key: value for key, value in viable.items() if tables[key][0].file_type == "xlsx"}
        viable = workbooks or viable
    located = {key: value for key, value in viable.items() if tables[key][0].table_row.sheet_name and re.search(
        rf"\b(?:in|on|from)\s+(?:the\s+)?{re.escape(tables[key][0].table_row.sheet_name)}(?!\w)", query, re.I)}
    viable = located or viable
    if len(viable) != 1:
        error = StructuredError("ambiguous_table", "Several tables support this question. Name the file and sheet to use.")
        error.diagnostic = {"table_candidates": traces}
        raise error
    key = next(iter(viable))
    plan, effective = viable[key]
    return key, plan, effective, traces


@dataclass(frozen=True)
class Number:
    value: Decimal
    unit: str = ""


def number(cell: str) -> Number:
    text = cell.strip().replace("\u00a0", " ")
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1].strip()
    units = {"$": "USD", "€": "EUR", "£": "GBP", "₹": "INR", "¥": "JPY"}
    unit = ""
    symbol = re.match(r"^([$€£₹¥])\s*", text)
    code = re.match(r"^(USD|EUR|GBP|INR|JPY|CAD|AUD)\s*", text, re.I)
    if symbol or code:
        match = symbol or code
        unit = units.get(match[1], match[1].upper())
        text = text[match.end():]
    if text.endswith("%"):
        if unit:
            raise StructuredError("invalid_numeric_cell", "A cell mixes currency and percentage units.")
        unit, text = "%", text[:-1].strip()
    suffix = re.search(r"\s+(USD|EUR|GBP|INR|JPY|CAD|AUD)$", text, re.I)
    if suffix:
        if unit and unit != suffix[1].upper():
            raise StructuredError("mixed_units", "A cell contains conflicting currency units.")
        unit, text = suffix[1].upper(), text[:suffix.start()]
    # Only valid comma thousands grouping is removed; locale ambiguity is refused.
    if not re.fullmatch(r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?", text):
        raise StructuredError("invalid_numeric_cell", f"Cannot calculate from the nonnumeric cell {cell!r}.")
    try:
        value = Decimal(text.replace(",", ""))
    except InvalidOperation as exc:
        raise StructuredError("invalid_numeric_cell", "The numeric cell cannot be parsed.") from exc
    return Number(-value if negative else value, unit)


@dataclass(frozen=True)
class Filter:
    column: int
    comparator: Comparator
    values: tuple[str, ...]


@dataclass(frozen=True)
class Plan:
    operation: Operation
    columns: tuple[int, ...]
    filters: tuple[Filter, ...] = ()


@dataclass(frozen=True)
class Execution:
    plan: Plan
    rows: tuple[Evidence, ...]
    inputs: tuple[Number, ...]
    value: Number | None


def table_complete(units: list[Evidence]) -> tuple[list[str], list[Evidence]]:
    if not units or any(unit.table_row is None for unit in units):
        raise StructuredError("table_metadata_missing", "Re-ingest this table to enable structured answers.")
    metadata = units[0].table_row
    headers = metadata.headers
    rows = sorted((unit for unit in units if not unit.table_row.is_header), key=lambda e: e.table_row.row_number)
    if (len([u for u in units if u.table_row.is_header]) != 1
        or len(rows) != metadata.data_row_count
        or len({u.table_row.row_number for u in units}) != len(units)
        or any(u.table_row.headers != headers or u.table_row.data_row_count != len(rows)
               or len(u.table_row.cells) != len(headers)
               or u.table_row.sheet_name != metadata.sheet_name for u in units)):
        raise StructuredError("incomplete_table", "The stored table is incomplete. Re-ingest it before calculating.")
    if any(u.snippet != u.table_row.quote() for u in units):
        raise StructuredError("cell_evidence_mismatch", "Stored cells do not match their evidence quotes.")
    return headers, rows


_OPERATORS = {
    ">=": "ge", "<=": "le", "!=": "ne", "==": "eq", "=": "eq", ">": "gt", "<": "lt",
    "at least": "ge", "at most": "le", "greater than": "gt", "more than": "gt", "above": "gt",
    "less than": "lt", "below": "lt", "over": "gt", "under": "lt", "not equal to": "ne", "equal to": "eq", "equals": "eq", "is": "eq",
}

_ROW_COUNT = r"\bcount\b|\b(?:how many|number of)\s+(?:rows|records|entries|employees|people|items|staff|workers|persons|products)\b"
_MONTHS = {name.casefold(): i for i in range(1, 13) for name in (calendar.month_name[i], calendar.month_abbr[i])}
_MONTH_PATTERN = "(?:" + "|".join(sorted(_MONTHS, key=len, reverse=True)) + ")"


def cell_mentioned(value: str, query: str) -> bool:
    """Cell identities are literal; stemming must not conflate Sale with Sales."""
    return bool(value.strip() and re.search(rf"(?<!\w){re.escape(value.strip())}(?!\w)", query, re.I))


def table_entity_mentioned(units: list[Evidence], query: str) -> bool:
    """Identify a table by a literal entity, without treating dates as entities."""
    labels = ("name", "person", "employee", "worker", "staff", "item", "product", "sku",
              "category", "team", "department", "dept", "division")
    for unit in units:
        row = unit.table_row
        if row is None or row.is_header:
            continue
        for header, value in zip(row.headers, row.cells):
            if (any(mentioned(label, header) for label in labels)
                    and re.search(r"[A-Za-z]", value) and cell_mentioned(value, query)):
                return True
    return False


def requested_operation(query: str, headers: list[str], rows: list[Evidence]) -> Operation:
    target = re.split(r"\b(?:where|with|whose|for)\b", query, maxsplit=1, flags=re.I)[0]
    target = re.sub(r'"[^\"]*"|\'[^\']*\'', " ", target)
    for header in sorted(headers, key=len, reverse=True):
        if header:
            target = re.sub(rf"(?<!\w){re.escape(header)}(?!\w)", " ", target, flags=re.I)
    for value in {cell for row in rows for cell in row.table_row.cells if re.search(r"[A-Za-z]", cell)}:
        target = re.sub(rf"(\b(?:of|does|did)\s+){re.escape(value)}(?!\w)|(?<!\w){re.escape(value)}(?=['’]s\b)", " ", target, flags=re.I)
    target = re.sub(r"\b(?:at most|at least|greater than|less than|more than)\b.*$", " ", target, flags=re.I)
    operations = {op for pattern, op in [
        (r"\b(?:average|mean|avg)\b", "average"), (r"\b(?:minimum|min|lowest|smallest|fewest)\b", "min"),
        (r"\b(?:maximum|max|highest|largest|most)\b", "max"), (r"\b(?:sum|total)\b", "sum"),
        (_ROW_COUNT, "count")] if re.search(pattern, target, re.I)}
    if "count" in operations and "sum" in operations and not re.search(r"\bsum\b", target, re.I):
        operations.remove("sum")  # "total number of rows" still counts rows.
    if len(operations) > 1:
        raise StructuredError("ambiguous_operation", "This asks for several operations. Ask for one calculation at a time.")
    operation = next(iter(operations), "lookup")
    if operation == "lookup" and re.search(r"\bhow many\s+(?:units|quantity|qty)\b", query, re.I) and re.search(
        r"\b(?:across|combined|altogether|through|between)\b", query, re.I):
        operation = "sum"
    if operation != "lookup" and re.search(r"\b(?:for each|group(?:ed)? by|per (?:team|department|category|product))\b", query, re.I):
        raise StructuredError("unsupported_operation", "Grouped calculations are not supported. Filter one group and name the operation.")
    return operation


def _month_columns(rows: list[Evidence], headers: list[str] | None = None) -> set[int]:
    headers = headers if headers is not None else (rows[0].table_row.headers if rows else [])
    return {i for i, header in enumerate(headers)
            if any(mentioned(label, header) for label in ("month", "period", "date"))
            and all(row.table_row.cells[i].strip().casefold() in _MONTHS for row in rows)}


def _month_filters(query: str, headers: list[str], rows: list[Evidence]):
    pattern = rf"\b(?:between\s+({_MONTH_PATTERN})\s+and\s+({_MONTH_PATTERN})|(?:from\s+)?({_MONTH_PATTERN})\s*(?:through|to|until|[-–])\s*({_MONTH_PATTERN}))\b"
    ranges = list(re.finditer(pattern, query, re.I))
    points = {int(_MONTHS[m[0].casefold()]) for m in re.finditer(rf"\b{_MONTH_PATTERN}\b", query, re.I)}
    candidates = _month_columns(rows, headers)
    if not candidates:
        if ranges:
            raise StructuredError("filter_unmapped", "The month range cannot be mapped to a stored month column.")
        return [], [], set()
    if not points:
        return [], [], set()
    explicit = {i for i in candidates if mentioned(headers[i], query)}
    candidates = explicit or candidates
    if len(candidates) != 1:
        raise StructuredError("ambiguous_filter", "Several columns contain months. Name the month column to filter.")
    index = next(iter(candidates))
    selected = set(points)
    spans = []
    for match in ranges:
        start, end = (_MONTHS[(match[1] or match[3]).casefold()], _MONTHS[(match[2] or match[4]).casefold()])
        current = start
        while True:
            selected.add(current)
            if current == end:
                break
            current = current % 12 + 1
        prefix = query[:match.start()]
        header = re.search(rf"(?<!\w){re.escape(headers[index])}\s*$", prefix, re.I)
        spans.append((header.start() if header else match.start(), match.end()))
    values = tuple(dict.fromkeys(row.table_row.cells[index] for row in rows
                               if _MONTHS[row.table_row.cells[index].strip().casefold()] in selected))
    return [Filter(index, "eq", values or tuple(calendar.month_name[i] for i in sorted(selected)))], spans, {index}


def _filter_prefixes(headers: list[str]) -> dict[str, set[int]]:
    prefixes = {header: {i} for i, header in enumerate(headers) if header}
    for labels, words in _COLUMN_VOCABULARY:
        columns = {i for i, header in enumerate(headers) if _header_matches(labels, header)}
        for word in words:
            if columns:
                prefixes.setdefault(word, set()).update(columns)
                plural = word[:-1] + "ies" if word.endswith("y") else word + "s"
                prefixes.setdefault(plural, set()).update(columns)
                if word == "earn":
                    for form in ("earned", "earning", "earnings"):
                        prefixes.setdefault(form, set()).update(columns)
    return prefixes


def plan_question(query: str, units: list[Evidence]) -> Plan:
    headers, rows = table_complete(units)
    query = re.sub(r"\s+in\s+(?:the\s+)?(?:[\w.-]+\.(?:csv|xlsx)|csv|excel|spreadsheet|table)\s*[?.]?$", "", query, flags=re.I)
    query = re.sub(r"^\s*may\s+(?:you|i)\b", "", query, flags=re.I)
    operation = requested_operation(query, headers, rows)
    target_question = re.split(r"\b(?:where|with|whose|for)\b", query, maxsplit=1, flags=re.I)[0]
    columns = mapped_columns(headers, target_question, counting=operation == "count")
    if operation not in {"count", "lookup"} and len(columns) != 1:
        raise StructuredError("column_unmapped", "I cannot map this calculation to one table column. Name the column explicitly.")
    if operation == "lookup" and not columns:
        raise StructuredError("column_unmapped", "I cannot map the question to a table column. Name the column explicitly.")
    if any(not normalized(headers[i]) or sum(normalized(h) == normalized(headers[i]) for h in headers) != 1
           for i in columns):
        raise StructuredError("ambiguous_column", "The requested column has a blank or duplicate header.")
    filters, matched_spans, explicit_columns = _month_filters(query, headers, rows)
    unquoted = re.sub(r'"[^\"]*"|\'[^\']*\'', " ", query)
    if re.search(r"\b(?:where|with|whose)\b.*\bor\b", unquoted, re.I):
        raise StructuredError("unsupported_filter", "OR comparison clauses are unsupported. Use one filter or a list of values on one column.")
    for prefix, candidates in sorted(_filter_prefixes(headers).items(), key=lambda item: len(item[0]), reverse=True):
        operators = "|".join(re.escape(op) for op in sorted(_OPERATORS, key=len, reverse=True))
        pattern = rf"(?<!\w){re.escape(prefix)}(?!\w)\s*({operators})\s*(\"[^\"]+\"|'[^']+'|[^?;]+?)(?=\s+and\s+|\s+in (?:the )?(?:csv|excel|spreadsheet)|[?;]|$)"
        for match in re.finditer(pattern, query, re.I):
            if any(match.start() < end and match.end() > start for start, end in matched_spans):
                continue
            if len(candidates) != 1:
                raise StructuredError("ambiguous_column", "A comparison word matches several columns. Name the exact header.")
            i = next(iter(candidates))
            value = match[2].strip().strip("\"'").rstrip(".")
            comparator = _OPERATORS[match[1].lower()]
            if comparator not in {"eq", "ne"}:
                number(value)
            filters.append(Filter(i, comparator, (value,)))
            explicit_columns.add(i)
            matched_spans.append(match.span())
    where = re.search(r"\bwhere\b", query, re.I)
    if where:
        remainder = list(query)
        for start, end in matched_spans:
            remainder[start:end] = " " * (end - start)
        unexplained = re.sub(r"\band\b|[?;.\s]", "", "".join(remainder)[where.end():], flags=re.I)
        if unexplained:
            raise StructuredError("filter_unmapped", "Part of the filter cannot be mapped to a table column.")
    if re.search(r"\bwhere\b|[<>!=]", query) and not filters:
        raise StructuredError("filter_unmapped", "I cannot map the filter to a column and comparison value.")
    if re.search(r"\b(?:above|below|over|under|at least|at most|greater than|less than|more than)\b", unquoted, re.I) and not any(f.comparator not in {"eq", "ne"} for f in filters):
        raise StructuredError("filter_unmapped", "The comparison cannot be bound to a column and numeric value.")
    implicit_query = list(query)
    for start, end in matched_spans:
        implicit_query[start:end] = " " * (end - start)
    implicit_query = "".join(implicit_query)
    for i in range(len(headers)):
        if i in explicit_columns:
            continue
        values = tuple(dict.fromkeys(row.table_row.cells[i] for row in rows
                       if row.table_row.cells[i] and cell_mentioned(row.table_row.cells[i], implicit_query)))
        # Implicit filters require text entities, never a stray numeric digit.
        values = tuple(v for v in values if re.search(r"[A-Za-z]", v))
        if values:
            filters.append(Filter(i, "eq", values))
    for entity in re.finditer(r"\b(?:for|of|in)\s+(.+?)(?=\s+(?:are|is|in|where|with|whose|on|from)\b|[?]|$)", query, re.I):
        text = entity[1].strip().rstrip(".")
        field_reference = normalized(text).removeprefix("the ")
        field_names = {normalized(h) for h in headers}
        field_names.update(normalized(word) for labels, words in _COLUMN_VOCABULARY for word in words
                           if any(_header_matches(labels, h) for h in headers))
        if (field_reference in field_names
            or (operation == "count" and re.fullmatch(r"rows?|records?|entries|employees?|people|items?|staff|workers?|persons?|products?", text, re.I))
            or re.fullmatch(r"(?:USD|EUR|GBP|INR|JPY|CAD|AUD|dollars?|euros?|rupees?|currency)", text, re.I)
            or any(cell_mentioned(cell, text) for row in rows for cell in row.table_row.cells if re.search(r"[A-Za-z]", cell))
            or (explicit_columns & _month_columns(rows) and re.search(rf"\b{_MONTH_PATTERN}\b", text, re.I))):
            continue
        raise StructuredError("filter_unmapped", "I cannot find the requested entity in the table cells.")
    return Plan(operation, columns, tuple(filters))


def matches(row: Evidence, filters: tuple[Filter, ...]) -> bool:
    for constraint in filters:
        cell = row.table_row.cells[constraint.column]
        if constraint.comparator in {"eq", "ne"}:
            equal = any(cell.strip().casefold() == value.strip().casefold() for value in constraint.values)
            try:
                left = number(cell)
                equal = equal or any(left.value == number(value).value
                                     and (not number(value).unit or left.unit == number(value).unit)
                                     for value in constraint.values)
            except StructuredError:
                pass
            if equal != (constraint.comparator == "eq"):
                return False
        else:
            left, right = number(cell), number(constraint.values[0])
            if left.unit != right.unit and right.unit:
                raise StructuredError("mixed_units", "Filter and column use different units.")
            comparisons = {"gt": left.value > right.value, "ge": left.value >= right.value,
                           "lt": left.value < right.value, "le": left.value <= right.value}
            if not comparisons[constraint.comparator]:
                return False
    return True


def execute(plan: Plan, units: list[Evidence]) -> Execution:
    headers, rows = table_complete(units)
    if any(i < 0 or i >= len(headers) for i in plan.columns) or any(
        f.column < 0 or f.column >= len(headers) for f in plan.filters):
        raise StructuredError("column_unmapped", "The plan refers to an unavailable column.")
    if any(not normalized(headers[f.column]) or sum(normalized(h) == normalized(headers[f.column]) for h in headers) != 1
           for f in plan.filters):
        raise StructuredError("ambiguous_column", "A filter column has a blank or duplicate header.")
    selected = tuple(row for row in rows if matches(row, plan.filters))
    if plan.operation == "count":
        return Execution(plan, selected, (), Number(Decimal(len(selected))))
    if not selected:
        raise StructuredError("no_matching_rows", "No rows match the requested filter.")
    if plan.operation == "lookup":
        return Execution(plan, selected, (), None)
    if len(plan.columns) != 1:
        raise StructuredError("column_unmapped", "A calculation requires exactly one column.")
    inputs = tuple(number(row.table_row.cells[plan.columns[0]]) for row in selected)
    units_present = {n.unit for n in inputs if n.unit}
    if len(units_present) > 1:
        raise StructuredError("mixed_units", "The selected cells have incompatible currency or percentage units.")
    if "%" in units_present and any(not n.unit for n in inputs):
        raise StructuredError("mixed_units", "Percentages cannot be mixed with unitless cells.")
    values = [n.value for n in inputs]
    if plan.operation == "sum":
        result = sum(values, Decimal(0))
    elif plan.operation == "average":
        result = sum(values, Decimal(0)) / len(values)
    elif plan.operation == "min":
        result = min(values)
    elif plan.operation == "max":
        result = max(values)
    else:
        raise StructuredError("unsupported_operation", "This table operation is not supported.")
    return Execution(plan, selected, inputs, Number(result, next(iter(units_present), "")))


def verify_execution(result: Execution, fresh_units: list[Evidence]) -> None:
    """Independently recompute using newly read cells, not execute()'s result."""
    _, rows = table_complete(fresh_units)
    selected = [row for row in rows if matches(row, result.plan.filters)]
    if [row.id for row in selected] != [row.id for row in result.rows]:
        raise StructuredError("calculation_verification_failed", "The selected rows changed before verification.")
    if any(fresh.table_row != old.table_row for fresh, old in zip(selected, result.rows)):
        raise StructuredError("calculation_verification_failed", "Stored cells changed before verification.")
    if result.plan.operation == "lookup":
        if result.value is not None or result.inputs:
            raise StructuredError("calculation_verification_failed", "Unexpected computed lookup value.")
        return
    if result.plan.operation == "count":
        verified = Number(Decimal(len(selected)))
    else:
        cells = [number(row.table_row.cells[result.plan.columns[0]]) for row in selected]
        if tuple(cells) != result.inputs or not cells:
            raise StructuredError("calculation_verification_failed", "Calculation inputs do not match stored cells.")
        # Separate accumulation and operation dispatch from the executor.
        total = Decimal(0)
        smallest = largest = cells[0].value
        for cell in cells:
            total += cell.value
            smallest = min(smallest, cell.value)
            largest = max(largest, cell.value)
        value = {"sum": total, "average": total / len(cells), "min": smallest, "max": largest}[result.plan.operation]
        verified = Number(value, next((cell.unit for cell in cells if cell.unit), ""))
    if result.value != verified:
        raise StructuredError("calculation_verification_failed", "The independently recomputed result disagrees.")


def verify_question_plan(query: str, plan: Plan, result: Execution, fresh_units: list[Evidence]) -> None:
    if result.plan != plan or plan_question(query, fresh_units) != plan:
        raise StructuredError("plan_verification_failed", "The executed operation or filters do not match the question's bound plan.")


def display_number(value: Number) -> str:
    digits = format(value.value, "f")
    if "." in digits:
        digits = digits.rstrip("0").rstrip(".")
    return f"{digits}%" if value.unit == "%" else f"{value.unit} {digits}".strip()


def answer_execution(query: str, result: Execution, table_units: list[Evidence]):
    """Return relevant cells as exact substrings of their canonical stored quotes."""
    from uuid import uuid4
    from app.domain.models import Citation
    citations: list[Citation] = []
    lines: list[str] = []

    def cite_cells(row: Evidence, columns: list[int]) -> None:
        metadata = row.table_row
        # Contiguous relevant cells form one exact source substring; gaps form
        # separate citations so unrelated columns are never included.
        groups: list[list[int]] = []
        for index in sorted(set(columns)):
            if groups and groups[-1][-1] + 1 == index:
                groups[-1].append(index)
            else:
                groups.append([index])
        for group in groups:
            quote = " | ".join(f"{metadata.headers[i]}: {metadata.cells[i]}" for i in group)
            if quote not in row.snippet:
                raise StructuredError("cell_evidence_mismatch", "A cited cell is absent from its stored row.")
            citations.append(Citation(id=f"cit_{uuid4().hex[:10]}", ordinal=len(citations) + 1,
                evidence_unit_id=row.id, snippet=quote, sheet_name=metadata.sheet_name,
                row_number=metadata.row_number, column=", ".join(metadata.headers[i] for i in group)))

    if result.plan.operation == "lookup":
        for row in result.rows:
            metadata = row.table_row
            columns = list(result.plan.columns)
            if re.search(r"\b(?:who|which|people|employees|persons)\b", query, re.I):
                columns = sorted(set(columns) | {i for i, h in enumerate(metadata.headers)
                                                if normalized(h) in {"name", "person", "employee", "full name"}})
            lines.append("; ".join(f"{metadata.headers[i]}: {metadata.cells[i]}" for i in columns))
            cite_cells(row, columns + [f.column for f in result.plan.filters])
        return "\n".join(lines), citations
    for row in result.rows or tuple(u for u in table_units if u.table_row.is_header):
        metadata = row.table_row
        index = result.plan.columns[0] if result.plan.operation != "count" else (
            result.plan.filters[0].column if result.plan.filters else 0)
        cite_cells(row, [index] + [f.column for f in result.plan.filters])
    output = display_number(result.value)
    if result.plan.operation == "count":
        inputs = " + ".join("1" for _ in result.rows) or "0 matching rows"
        return f"Count: {inputs} = {output}", citations
    column = table_units[0].table_row.headers[result.plan.columns[0]]
    inputs = [display_number(n) for n in result.inputs]
    if result.plan.operation == "sum":
        expression = " + ".join(inputs)
    elif result.plan.operation == "average":
        expression = f"({' + '.join(inputs)}) / {len(inputs)}"
    else:
        expression = f"{result.plan.operation}({', '.join(inputs)})"
    return f"{column}: {expression} = {output}", citations


def select_keys(query: str, units: list[Evidence]) -> list[Evidence]:
    """Resolve keys/paths, excluding incidental attribute values and prose."""
    terms = set(normalized(query).split()) - {
        "what", "which", "is", "are", "the", "a", "in", "of", "file", "document", "config",
        "json", "yaml", "xml", "value", "key", "listed", "list", "say", "does", "it", "show"}
    scores = {}
    for unit in units:
        key = unit.key_value
        if not key:
            continue
        key_terms = set(normalized(" ".join(key.keys)).split())
        overlap = terms & key_terms
        if overlap and (key.value_type != "attribute" or any(normalized(k).lstrip("@") in terms for k in key.keys[-1:])):
            leaf = int(mentioned(key.keys[-1] if key.keys else "", query))
            scores[unit.id] = (key.path in query, len(overlap) + leaf)
    if not scores:
        raise StructuredError("key_unmapped", "I cannot map the question to a stored key or element path. Name the key or path explicitly.")
    best = max(scores.values())
    selected = [u for u in units if scores.get(u.id) == best]
    docs = {u.document_id for u in selected}
    if len(docs) != 1:
        raise StructuredError("ambiguous_key", "Several documents contain this key. Name the file and full path.")
    collection = bool(re.search(r"\b(?:items|list|listed|values|elements)\b", query, re.I))
    if len(selected) > 1 and not collection:
        raise StructuredError("ambiguous_key", "Several paths contain this key. Name the full path.")
    return selected
