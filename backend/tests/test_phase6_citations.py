from docx import Document

from tests.test_ingestion import client_with_data_root
from tests.test_phase5_answers import ask, upload
from tests.test_phase6_parsing import payload


def test_docx_answer_and_evidence_lookup_agree_on_real_page(tmp_path):
    document = Document()
    document.add_paragraph("The beacon code is AMBER.")
    paragraph = document.add_paragraph("The beacon code is CEDAR.")
    paragraph.paragraph_format.page_break_before = True
    with client_with_data_root(tmp_path) as client:
        doc = upload(client, "guide.docx", payload(document))
        response = ask(client, "What is the beacon code on the second page?", doc)
        assert response["grounded"]
        assert "CEDAR" in response["answer"] and "AMBER" not in response["answer"]
        assert response["citations"]
        for citation in response["citations"]:
            evidence = client.get('/api/v1/evidence/' + citation["evidence_unit_id"]).json()
            assert citation["page"] == evidence["page"] == 2
            assert citation["snippet"] in evidence["snippet"]
