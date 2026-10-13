import io
from dataclasses import replace
from decimal import Decimal

import openpyxl
import pytest

from app.services import structured
from tests.test_ingestion import client_with_data_root


def upload(client, name, payload):
    response = client.post("/api/v1/documents", files=[("files", (name, payload, "application/octet-stream"))])
    assert response.status_code == 201, response.text
    return response.json()["items"][0]["document"]["id"]


def ask(client, query, document=None):
    payload = {"query": query}
    if document:
        payload["scope"] = {"type": "document", "document_id": document}
    response = client.post("/api/v1/ask", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def test_total_is_verified_and_cites_only_exact_input_cells(tmp_path):
    with client_with_data_root(tmp_path) as client:
        doc = upload(client, "ledger.csv", b'Period,Receipts,Secret\nApr,"1,100",hidden-one\nMay,300,hidden-two\nJun,200,hidden-three\n')
        result = ask(client, "Total Receipts for April and May in ledger.csv?", doc)
        assert result["grounded"]
        assert result["answer"] == "Receipts: 1100 + 300 = 1400"
        assert result["provider"]["name"] == "deterministic"
        assert result["diagnostic"]["verified"] is True
        assert [c["row_number"] for c in result["citations"]] == [2, 3]
        assert [c["snippet"] for c in result["citations"]] == ["Period: Apr | Receipts: 1,100", "Period: May | Receipts: 300"]
        assert "Secret" not in str(result)


def test_lookup_only_returns_requested_cells_and_unknown_column_refuses(tmp_path):
    with client_with_data_root(tmp_path) as client:
        doc = upload(client, "parts.csv", b"Product,Units,Private\nScrew,11,secret\nNut,23,secret\n")
        result = ask(client, "What are the Units for Nut?", doc)
        assert result["answer"] == "Units: 23"
        assert len(result["citations"]) == 1
        assert result["citations"][0]["row_number"] == 3
        assert result["citations"][0]["snippet"] == "Product: Nut | Units: 23"
        result = ask(client, "What is the warranty period in parts.csv?", doc)
        assert not result["grounded"]
        assert result["refusal_reason"] == "column_unmapped"
        assert "column" in result["refusal_detail"]
        assert not result["citations"]


def test_changed_executor_result_is_refused_by_independent_verifier(tmp_path, monkeypatch):
    original = structured.execute
    def incorrect(plan, units):
        result = original(plan, units)
        return replace(result, value=structured.Number(Decimal("99999")))
    monkeypatch.setattr(structured, "execute", incorrect)
    with client_with_data_root(tmp_path) as client:
        doc = upload(client, "totals.csv", b"Category,Amount\nOne,13\nTwo,17\n")
        result = ask(client, "Sum Amount", doc)
        assert result["refusal_reason"] == "calculation_verification_failed"
        assert result["answer"] is None


def test_excel_hint_and_generic_spreadsheet_choose_workbook(tmp_path):
    buffer = io.BytesIO()
    workbook = openpyxl.Workbook()
    workbook.active.title = "Ledger"
    workbook.active.append(["Category", "Amount"])
    workbook.active.append(["One", 41])
    workbook.save(buffer)
    with client_with_data_root(tmp_path) as client:
        csv_id = upload(client, "other.csv", b"Category,Amount\nOne,999\n")
        xlsx_id = upload(client, "book.xlsx", buffer.getvalue())
        for query in ["Sum Amount in Excel", "Sum Amount in the spreadsheet"]:
            result = ask(client, query)
            assert result["answer"] == "Amount: 41 = 41"
            evidence = client.get("/api/v1/evidence/" + result["citations"][0]["evidence_unit_id"]).json()
            assert evidence["document_id"] == xlsx_id
        assert not ask(client, "Sum Amount in Excel", csv_id)["grounded"]


def test_ambiguous_tables_and_invalid_numeric_cells_refuse(tmp_path):
    with client_with_data_root(tmp_path) as client:
        upload(client, "one.csv", b"Person,Amount\nZed,13\n")
        upload(client, "two.csv", b"Person,Amount\nZed,19\n")
        assert ask(client, "Sum Amount")["refusal_reason"] == "ambiguous_table"
        doc = upload(client, "bad.csv", b"Person,Amount\nZed,missing\n")
        assert ask(client, "Sum Amount", doc)["refusal_reason"] == "invalid_numeric_cell"


@pytest.mark.parametrize("suffix,payload", [
    ("csv", b"Product,Price\nCog,unavailable\n"),
    ("json", b'{"price":"unavailable"}'),
    ("yaml", b'price: unavailable'),
    ("xml", b'<root><price>unavailable</price></root>'),
])
def test_structured_lookup_preserves_numeric_answer_type_gate(tmp_path, suffix, payload):
    with client_with_data_root(tmp_path) as client:
        doc = upload(client, f"costs.{suffix}", payload)
        result = ask(client, f"What is the price in USD in costs.{suffix}?", doc)
        assert not result["grounded"]
        assert result["refusal_reason"] == "answer_type_missing"
        assert result["citations"] == []
        available = upload(client, f"available.{suffix}", payload.replace(b"unavailable", b"USD 17.50"))
        result = ask(client, "What is the price in USD?", available)
        assert result["grounded"]
        assert "17.50" in result["answer"]
