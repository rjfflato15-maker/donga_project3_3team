from backend.scripts.prepare_hard_dataset import CONDITIONS, plan
from backend.evaluation_core import verify_dataset
from backend.evaluation_review import validate_reference_draft


def test_hard_corpus_has_disjoint_templates_and_predeclared_condition_coverage():
    manifest, designs = plan()
    dev = [row for row in manifest["contracts"] if row["split"] == "dev"]
    test = [row for row in manifest["contracts"] if row["split"] == "test"]
    assert {row["condition"] for row in dev} == {row["condition"] for row in test} == set(CONDITIONS)
    assert not {row["layout_family"] for row in dev} & {row["layout_family"] for row in test}
    assert len({doc["document_id"] for row in manifest["contracts"] for doc in row["documents"]}) == 72


def test_unreadable_stamp_total_is_review_even_when_generator_knows_amount():
    manifest, designs = plan()
    estimates = [design for design in designs.values() if design["document_type"] == "estimate" and design["condition"] == "stamp"]
    assert len(estimates) == 2
    for estimate in estimates:
        assert estimate["fields"]["total_amount"] == {"state": "REVIEW", "value": None}
        assert estimate["fields"]["supply_amount"]["state"] == "VALUE"
