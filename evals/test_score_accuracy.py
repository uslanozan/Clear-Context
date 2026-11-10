from score_accuracy import outcome


def test_true_claims_must_be_supported_and_never_contradicted():
    assert outcome("true", ["supported", "insufficient"]) == "correct"
    assert outcome("true", ["supported", "contradicted"]) == "wrong"
    assert outcome("true", ["insufficient"]) == "unsettled"


def test_false_and_half_claims_need_a_contradicted_detail():
    assert outcome("false", ["supported", "contradicted"]) == "correct"
    assert outcome("half", ["contradicted"]) == "correct"
    assert outcome("false", ["supported"]) == "wrong"
    assert outcome("half", ["not_assessed"]) == "unsettled"


def test_unsettleable_claims_must_not_be_settled():
    assert outcome("unsettleable", []) == "correct"
    assert outcome("unsettleable", ["insufficient"]) == "correct"
    assert outcome("unsettleable", ["supported"]) == "wrong"
