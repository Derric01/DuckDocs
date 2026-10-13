"""Schema-based natural wording, independent of public/private test fixtures."""
import pytest

from app.services.structured import StructuredError, execute, plan_question
from tests.test_phase5_executor import table


@pytest.mark.parametrize("question", ["How much does Nora earn?", "What is Nora's pay?", "What are the wages for Nora?"])
def test_pay_wording_binds_unique_stored_salary_header(question):
    units = table(b'Employee Name,Division,Annual Salary\nNora,Blue,8100\nPia,Blue,9400\nOmar,Red,6700\n')
    plan = plan_question(question, units)
    result = execute(plan, units)
    assert plan.operation == "lookup"
    assert plan.columns == (2,)
    assert [r.table_row.cells[0] for r in result.rows] == ["Nora"]
    assert result.rows[0].table_row.cells[2] == "8100"


@pytest.mark.parametrize("question", ["How many staff are in Blue?", "What is the number of workers in Blue?"])
def test_count_wording_does_not_require_column_name(question):
    units = table(b'Person,Team,Salary\nNora,Blue,8100\nPia,Blue,9400\nOmar,Red,6700\n')
    result = execute(plan_question(question, units), units)
    assert result.plan.operation == "count"
    assert result.value.value == 2


def test_unit_wording_binds_stored_quantity_and_entity():
    units = table(b'Product,Quantity\nCog,17\nBolt,29\n')
    result = execute(plan_question("How many units of Cog are available?", units), units)
    assert result.plan.columns == (1,)
    assert len(result.rows) == 1
    assert result.rows[0].table_row.cells[1] == "17"


def test_aliases_do_not_guess_unknown_or_ambiguous_attributes():
    units = table(b'Person,Gross Pay,Net Pay\nNora,9000,7100\n')
    for query in ["What is Nora's pay?", "What is Nora's warranty?"]:
        with pytest.raises(StructuredError) as error:
            plan_question(query, units)
        assert error.value.code in {"column_unmapped", "ambiguous_column"}
    assert plan_question("What is the Net Pay for Nora?", units).columns == (2,)
