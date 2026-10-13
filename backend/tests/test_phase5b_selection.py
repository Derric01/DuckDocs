import io

import openpyxl
import pytest

from tests.test_ingestion import client_with_data_root
from tests.test_phase5_answers import ask, upload


def workbook(sheets):
    book = openpyxl.Workbook()
    book.remove(book.active)
    for title, rows in sheets:
        sheet = book.create_sheet(title)
        for row in rows:
            sheet.append(row)
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


@pytest.mark.parametrize("reverse", [False, True])
def test_named_sheet_overrides_row_frequency_and_does_not_become_entity_filter(tmp_path, reverse):
    sheets = [("North", [["Product", "Units"], ["South", 999], ["South", 999], ["South", 999]]),
              ("South", [["Product", "Units"], ["Cog", 19], ["Bolt", 23]])]
    with client_with_data_root(tmp_path) as client:
        doc = upload(client, "stores.xlsx", workbook(list(reversed(sheets)) if reverse else sheets))
        result = ask(client, "Sum Units on the South sheet", doc)
        assert result["grounded"]
        assert result["answer"] == "Units: 19 + 23 = 42"
        assert {c["sheet_name"] for c in result["citations"]} == {"South"}
        assert result["diagnostic"]["structured_plan"]["operation"] == "sum"
        unknown = ask(client, "Sum Units on the Missing sheet", doc)
        assert not unknown["grounded"]
        assert unknown["refusal_reason"] == "sheet_unmapped"


def test_available_wording_uses_named_sheet_and_exact_product(tmp_path):
    with client_with_data_root(tmp_path) as client:
        doc = upload(client, "stores.xlsx", workbook([
            ("Dispatch", [["Product", "Units"], ["Gear", 800], ["Gear", 900]]),
            ("Warehouse", [["Item", "Stock"], ["Gear", 31], ["Cog", 47]])]))
        result = ask(client, "How many units of Gear are available in the Warehouse sheet?", doc)
        assert result["answer"] == "Stock: 31"
        assert {c["sheet_name"] for c in result["citations"]} == {"Warehouse"}


def test_schema_feasibility_beats_frequency_of_incidental_entity_mentions(tmp_path):
    with client_with_data_root(tmp_path) as client:
        doc = upload(client, "business.xlsx", workbook([
            ("Notes", [["Topic", "Note"], ["Nora", "Nora"], ["Nora", "Nora"], ["Nora", "Nora"]]),
            ("Payroll", [["Person", "Salary"], ["Nora", 7900], ["Omar", 6300]])]))
        result = ask(client, "What does Nora earn?", doc)
        assert result["answer"] == "Salary: 7900"
        assert {c["sheet_name"] for c in result["citations"]} == {"Payroll"}


def test_truly_ambiguous_matching_sheets_still_refuse(tmp_path):
    with client_with_data_root(tmp_path) as client:
        doc = upload(client, "ambiguous.xlsx", workbook([
            ("North", [["Product", "Units"], ["Gear", 11]]),
            ("South", [["Product", "Units"], ["Gear", 29]])]))
        assert ask(client, "What Units are recorded for Gear?", doc)["refusal_reason"] == "ambiguous_table"


@pytest.mark.parametrize("payload,question", [
    (b'Product,Unit Price\nCog,19\n', "How many units of Cog are available?"),
    (b'Person,Salary Band\nNora,7\n', "How much does Nora earn?"),
])
def test_identified_entity_with_missing_measure_does_not_fall_through_to_model(tmp_path, payload, question):
    with client_with_data_root(tmp_path) as client:
        upload(client, "records.csv", payload)
        result = ask(client, question)
        assert not result["grounded"]
        assert result["provider"]["name"] == "deterministic"
        assert result["refusal_reason"] == "column_unmapped"


def test_calendar_word_is_not_a_table_entity_anchor(tmp_path):
    with client_with_data_root(tmp_path) as client:
        upload(client, "periods.csv", b'Month,Units\nJanuary,99\n')
        upload(client, "museum.txt", b'In January the museum entrance fee is JPY 24 per visitor. The archive is open daily.')
        result = ask(client, "What entrance fee is charged at the museum in January?")
        assert result["grounded"]
        assert "24" in result["answer"]
        assert result["provider"]["name"] != "deterministic"
