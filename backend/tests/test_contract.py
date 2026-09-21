"""Published JSON schemas accept the checked-in examples and the API."""

import json
from pathlib import Path

import jsonschema
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = ROOT / "schemas"
EXAMPLES = SCHEMAS / "examples"


def _validator(name: str) -> Draft202012Validator:
    schema = json.loads((SCHEMAS / name).read_text())
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def test_examples_match_schemas():
    pairs = [
        ("tool_state.schema.json", "tool_state.json"),
        ("alarm.schema.json", "alarm_set.json"),
        ("lot_move.schema.json", "lot_move.json"),
    ]
    for schema_name, example_name in pairs:
        document = json.loads((EXAMPLES / example_name).read_text())
        _validator(schema_name).validate(document)


def test_examples_ingest_through_the_api(client):
    for name in ("tool_state.json", "alarm_set.json", "lot_move.json"):
        document = json.loads((EXAMPLES / name).read_text())
        response = client.post("/api/events", json=document)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "accepted"

    alarms = client.get("/api/alarms?open_only=true")
    assert alarms.status_code == 200
    assert any(row["alarm_code"] == "CHAMBER_PRESSURE" for row in alarms.json())

    lots = client.get("/api/lots")
    assert any(row["id"] == "L260921-001" and row["status"] == "COMPLETE" for row in lots.json())
