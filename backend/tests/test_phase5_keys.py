import pytest

from app.core.config import Settings
from app.services.chunking import chunk_document
from app.services.parsing import parse_key_values
from tests.test_ingestion import client_with_data_root
from tests.test_phase5_answers import ask, upload


@pytest.mark.parametrize("suffix,payload", [
    ("json", b'{"service":{"token":"LOCAL-XYZ","port":8123},"noise":"unrelated"}'),
    ("yaml", b'service:\n  token: LOCAL-XYZ\n  port: 8123\nnoise: unrelated\n'),
    ("xml", b'<service><token>LOCAL-XYZ</token><port>8123</port><noise>unrelated</noise></service>'),
])
def test_key_value_answers_are_exact_and_only_relevant(tmp_path, suffix, payload):
    with client_with_data_root(tmp_path) as client:
        doc = upload(client, f"settings.{suffix}", payload)
        result = ask(client, f"What is the token value in the {suffix} file?", doc)
        assert result["grounded"]
        assert "LOCAL-XYZ" in result["answer"]
        assert "unrelated" not in str(result)
        assert "8123" not in str(result)
        assert len(result["citations"]) == 1
        citation = result["citations"][0]
        assert citation["key_path"].endswith("token")
        evidence = client.get("/api/v1/evidence/" + citation["evidence_unit_id"]).json()
        assert citation["snippet"] == evidence["snippet"]
        assert evidence["key_value"]["path"] == citation["key_path"]
        unknown = ask(client, f"What is the absent_key value in the {suffix} file?", doc)
        assert unknown["refusal_reason"] == "key_unmapped"


def test_xml_collection_excludes_attributes_and_other_elements(tmp_path):
    with client_with_data_root(tmp_path) as client:
        doc = upload(client, "list.xml", b'<catalog revision="ignore"><item id="private">Sprocket</item><item>Cog</item><note>irrelevant</note></catalog>')
        result = ask(client, "What items are listed in the XML file?", doc)
        assert result["answer"] == "/catalog/item[1]: Sprocket\n/catalog/item[2]: Cog"
        assert len(result["citations"]) == 2
        assert "private" not in str(result)
        assert "irrelevant" not in str(result)
        attribute = ask(client, "What is the id at /catalog/item[1]/@id?", doc)
        assert "private" in attribute["answer"]


def test_nested_json_paths_lists_and_ambiguous_leaf(tmp_path):
    with client_with_data_root(tmp_path) as client:
        doc = upload(client, "nested.json", b'{"primary":{"token":"abc"},"backup":{"token":"def"},"items":["oak","pine"]}')
        assert ask(client, "What is token?", doc)["refusal_reason"] == "ambiguous_key"
        assert ask(client, "What is $.primary.token?", doc)["answer"] == '$.primary.token: "abc"'
        result = ask(client, "List the items", doc)
        assert result["answer"] == '$.items[0]: "oak"\n$.items[1]: "pine"'


@pytest.mark.parametrize("suffix,payload", [
    ("json", b'{"x":1,"x":2}'), ("json", b'{"x": NaN}'),
    ("yaml", b'x: 1\nx: 2'), ("yaml", b'x: &x [*x]'),
    ("yaml", b'!!python/object/apply:os.system ["echo bad"]'),
    ("xml", b'<!DOCTYPE x [<!ENTITY e "secret">]><x>&e;</x>'),
])
def test_unsafe_or_ambiguous_structured_payloads_are_rejected(suffix, payload):
    assert parse_key_values(payload, suffix) is None


def test_paths_keep_special_keys_and_typed_empty_values():
    parsed = parse_key_values(b'{"a.b":null,"empty":[],"flag":false}', "json")
    chunks = chunk_document(parsed, Settings(chunk_max_words=1, chunk_overlap_words=0))
    assert [c.key_value.path for c in chunks] == ['$["a.b"]', '$.empty', '$.flag']
    assert [c.key_value.value for c in chunks] == ["null", "[]", "false"]
    assert all(c.key_value.unit_count == 3 for c in chunks)
