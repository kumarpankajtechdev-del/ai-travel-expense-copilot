from pathlib import Path

from expense_ai_copilot.services.policy_retriever import PolicyRetriever


def test_policy_retriever_returns_relevant_hotel_policy():
    retriever = PolicyRetriever(Path("sample_data/policies"))

    chunks = retriever.retrieve("L4 hotel Mumbai INR 4200", top_k=1)

    assert chunks
    assert "L4" in chunks[0].text
    assert "INR 5000" in chunks[0].text
