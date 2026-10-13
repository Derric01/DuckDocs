from dataclasses import replace

import pytest

from app.services import structured
from tests.test_phase5_executor import table
from tests.test_ingestion import client_with_data_root
from tests.test_phase5_answers import ask, upload


@pytest.mark.parametrize("phrase", ["from February through April", "between Feb and Apr", "February-April"])
def test_month_ranges_include_intermediate_rows(phrase):
    units = table(b'Month,Units\nJan,13\nFeb,29\nMar,41\nApr,53\nMay,67\n')
    result = structured.execute(structured.plan_question(f"Total Units {phrase}", units), units)
    assert [row.table_row.cells[0] for row in result.rows] == ["Feb", "Mar", "Apr"]
    assert result.value.value == 123


def test_month_list_and_range_have_different_meaning():
    units = table(b'Month,Units\nFeb,29\nMar,41\nApr,53\n')
    result = structured.execute(structured.plan_question("Total Units for February and April", units), units)
    assert result.value.value == 82
    result = structured.execute(structured.plan_question("How many units across February through April?", units), units)
    assert result.plan.operation == "sum"
    assert result.value.value == 123


def test_average_uses_requested_operation_and_filter_column_is_not_measure():
    units = table(b'Person,Team,Salary\nNora,Blue,8100\nPia,Blue,9300\nOmar,Red,6700\n')
    result = structured.execute(structured.plan_question("Average pay for the Blue team", units), units)
    assert result.plan.columns == (2,)
    assert result.value.value == 8700
    result = structured.execute(structured.plan_question("How many staff earn above 8500?", units), units)
    assert result.plan.operation == "count"
    assert result.value.value == 1


@pytest.mark.parametrize("phrase,count", [("earns over 8500", 1), ("earn at most 8500", 2)])
def test_pay_comparisons_bind_inflected_verbs_and_do_not_select_maximum(phrase, count):
    units = table(b'Person,Team,Salary\nNora,Blue,8100\nPia,Blue,9300\nOmar,Red,6700\n')
    result = structured.execute(structured.plan_question(f"How many staff {phrase}?", units), units)
    assert result.plan.operation == "count"
    assert result.value.value == count
    assert result.plan.filters


def test_range_wraps_year_end_and_literal_entities_are_not_stemmed():
    units = table(b'Month,Units\nNov,13\nDec,29\nJan,41\nFeb,53\nMar,67\n')
    result = structured.execute(structured.plan_question("Sum Units from December to February", units), units)
    assert result.value.value == 123
    units = table(b'Product,Units\nSale,19\nSales,31\n')
    result = structured.execute(structured.plan_question("What Units are recorded for Sale?", units), units)
    assert len(result.rows) == 1
    assert result.rows[0].table_row.cells[1] == "19"


def test_person_names_that_are_months_do_not_create_a_calendar_column():
    units = table(b'Person,Salary\nApril,9000\nJune,7000\n')
    with pytest.raises(structured.StructuredError, match="month column"):
        structured.plan_question("Sum Salary between April and June", units)
    assert len(structured.execute(structured.plan_question("Salary for April", units), units).rows) == 1


def test_empty_table_month_filter_can_count_zero_without_invented_inputs():
    units = table(b'Month,Units\n')
    result = structured.execute(structured.plan_question("Count rows between February and April", units), units)
    assert result.value.value == 0


def test_entity_named_like_operation_does_not_change_lookup():
    units = table(b'Product,Units\nTotal,19\nMean,23\nOther,31\n')
    for name, value in [("Total", "19"), ("Mean", "23")]:
        plan = structured.plan_question(f"What Units are recorded for {name}?", units)
        assert plan.operation == "lookup"
        assert structured.execute(plan, units).rows[0].table_row.cells[1] == value


@pytest.mark.parametrize("query", [
    "Sum and average Amount", "Sum Amount where Team equals Blue or Team equals Red",
    "Total Amount for each Team", "Count rows where Team equals Blue and Missing > 3",
    "How many staff in Green?",
])
def test_unsupported_or_unbound_constraints_are_not_silently_ignored(query):
    units = table(b'Person,Team,Amount\nNora,Blue,11\nPia,Red,17\n')
    with pytest.raises(structured.StructuredError):
        structured.plan_question(query, units)


def test_executor_cannot_replace_question_plan_even_with_correct_arithmetic(tmp_path, monkeypatch):
    original = structured.execute
    def altered(plan, units):
        return original(replace(plan, operation="max"), units)
    monkeypatch.setattr(structured, "execute", altered)
    with client_with_data_root(tmp_path) as client:
        doc = upload(client, "values.csv", b'Category,Amount\nOne,17\nTwo,29\n')
        result = ask(client, "Sum Amount", doc)
        assert not result["grounded"]
        assert result["refusal_reason"] == "plan_verification_failed"


def test_computed_api_answer_exposes_bound_plan_and_exact_range_rows(tmp_path):
    with client_with_data_root(tmp_path) as client:
        doc = upload(client, "periods.csv", b'Month,Units,Private\nFeb,29,x\nMar,41,x\nApr,53,x\nMay,67,x\n')
        result = ask(client, "Average Units between February and April", doc)
        assert result["answer"] == "Units: (29 + 41 + 53) / 3 = 41"
        assert [c["row_number"] for c in result["citations"]] == [2, 3, 4]
        assert result["diagnostic"]["plan_verified"]
        assert result["diagnostic"]["structured_plan"]["operation"] == "average"
        assert "Private" not in str(result)
