from cap_evolve import target_profile as tp


def test_metadata_payload_shape():
    p = tp.resolve("gpt-oss-120b")
    payload = {"model": p.model, "tier": p.tier,
               "suggested_num_trials": p.suggested_num_trials,
               "resolution_note": p.resolution_note}
    assert payload == {"model": "gpt-oss-120b", "tier": "mid",
                       "suggested_num_trials": 5, "resolution_note": ""}
