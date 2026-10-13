from decimal import Decimal

import pytest

from app.core.config import Settings
from app.domain.models import Evidence
from app.services.chunking import chunk_document
from app.services.parsing import parse_csv
from app.services.structured import StructuredError, execute, number, plan_question


def table(payload=b'Person,Team,Amount,Rate\nNora,Blue,"$1,250.50",10%\nOmar,Red,$750.25,20%\nPia,Blue,$100.25,30%\n'):
    return [Evidence(id=f"e{i}", document_id="d", document_name="sample.csv", section=c.section,
                     page=1, line_start=c.line_start, line_end=c.line_end, snippet=c.text,
                     retrieval_score=1, relevance="High", table_row=c.table_row, file_type="csv")
            for i, c in enumerate(chunk_document(parse_csv(payload), Settings()))]


@pytest.mark.parametrize("question,value", [
    ("Sum Amount", "2101.00"), ("Average Amount", str(Decimal("2101") / 3)),
    ("Minimum Amount", "100.25"), ("Maximum Amount", "1250.50"),
    ("Count rows where Team equals Blue", "2"),
    ("Sum Amount where Amount >= $750", "2000.75"),
    ("Sum Amount for Blue", "1350.75"),
    ("Sum Amount where Team equals Blue and Amount > $500", "1250.50"),
    ("Sum Amount where Team equals 'Blue'", "1350.75"),
    ("Average Rate", "20"),
])
def test_plans_and_operations(question, value):
    units = table()
    result = execute(plan_question(question, units), units)
    assert result.value.value == Decimal(value)


@pytest.mark.parametrize("cell,value,unit", [("1,234.50", "1234.50", ""), ("€2,000", "2000", "EUR"),
    ("(GBP 42.5)", "-42.5", "GBP"), ("12.5%", "12.5", "%"), ("50 CAD", "50", "CAD")])
def test_numeric_formats(cell, value, unit):
    assert number(cell).value == Decimal(value)
    assert number(cell).unit == unit


@pytest.mark.parametrize("cell", ["1,23", "NaN", "inf", "one", "", "1.2.3", "$10%", "=SUM(A1:A3)"])
def test_invalid_cells_never_become_zero_or_code(cell):
    with pytest.raises(StructuredError):
        number(cell)


def test_empty_count_and_unmapped_column():
    units = table()
    result = execute(plan_question("Count rows where Team equals Green", units), units)
    assert result.value.value == 0
    with pytest.raises(StructuredError, match="column"):
        plan_question("Total bonuses", units)
    with pytest.raises(StructuredError, match="entity"):
        plan_question("Amount for Zed", units)


def test_incomplete_table_and_mixed_units_refuse():
    units = table()
    with pytest.raises(StructuredError, match="incomplete"):
        execute(plan_question("Sum Amount", units), units[:-1])
    units[-1].table_row.cells[2] = "€100"
    units[-1].snippet = units[-1].table_row.quote()
    with pytest.raises(StructuredError, match="incompatible"):
        execute(plan_question("Sum Amount", units), units)


def test_comparison_and_not_equal_filters():
    units = table()
    for operator, expected in [("<", 2), ("<=", 2), (">", 1), (">=", 1), ("!=", 2)]:
        plan = plan_question(f"Count rows where Amount {operator} $1000", units)
        assert execute(plan, units).value.value == (3 if operator == "!=" else expected)
    plan = plan_question("Amount where Team not equal to Blue", units)
    assert [r.table_row.cells[0] for r in execute(plan, units).rows] == ["Omar"]
