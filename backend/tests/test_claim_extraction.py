from __future__ import annotations

from app.services.ml import claim_extraction


def test_find_claim_candidates_only_looks_at_claim_sections():
    text = "Our model achieved 94.2% accuracy, outperforming the previous baseline by 3 points."
    assert claim_extraction.find_claim_candidates(text, "results") != []
    assert claim_extraction.find_claim_candidates(text, "references") == []


def test_find_claim_candidates_requires_evidence_or_cue():
    text = "The sky was blue that day and the researchers went for lunch before continuing their work."
    assert claim_extraction.find_claim_candidates(text, "results") == []


def test_find_limitation_candidates_only_looks_at_limitation_sections():
    text = "A key limitation of this work is the small dataset size, which may not generalize."
    assert claim_extraction.find_limitation_candidates(text, "limitations") != []
    assert claim_extraction.find_limitation_candidates(text, "methodology") == []


def test_normalize_claims_drops_items_whose_evidence_is_not_a_real_candidate(monkeypatch):
    """This is the core anti-hallucination guardrail: normalize_claims
    must discard any LLM output item whose evidence_text doesn't match
    one of the candidate sentences it was actually given."""

    class FakeProvider:
        def generate(self, system_prompt, user_prompt):
            import json

            return json.dumps(
                [
                    {
                        "claim_text": "The model reaches 90% accuracy.",
                        "claim_type": "result",
                        "evidence_text": "Our model achieved 90% accuracy on the benchmark.",
                    },
                    {
                        "claim_text": "A completely invented claim not in the candidates.",
                        "claim_type": "finding",
                        "evidence_text": "This sentence was never provided as a candidate at all.",
                    },
                ]
            )

    monkeypatch.setattr(claim_extraction, "get_llm_provider", lambda: FakeProvider())

    candidates = ["Our model achieved 90% accuracy on the benchmark."]
    results = claim_extraction.normalize_claims(candidates)

    assert len(results) == 1
    assert results[0]["claim_text"] == "The model reaches 90% accuracy."
