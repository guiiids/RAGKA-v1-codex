import pytest
from rag_assistant_v2 import FlaskRAGAssistantV2

@pytest.fixture
def dummy_results():
    # Simulate knowledge base search results
    return [
        {
            "chunk": "Test procedural step 1. Test procedural step 2.",
            "title": "Test Source A",
            "parent_id": "doc_a",
            "relevance": 1.0
        },
        {
            "chunk": "Informational about product X.",
            "title": "Test Source B",
            "parent_id": "doc_b",
            "relevance": 0.8
        }
    ]

def test_citation_ids_and_mapping(monkeypatch, dummy_results):
    # Patch search_knowledge_base to return dummy results
    def fake_search(self, query):
        return dummy_results

    # Patch OpenAIService.get_chat_response to return a canned answer
    def fake_get_chat_response(self, messages, **kwargs):
        # Use the standard citation format with IDs present in sources
        return "The procedure [S_12345678_aaaaaaaa] and the informational [S_12345679_bbbbbbbb] steps."

    # Patch generate_unique_source_id so IDs are deterministic
    def fake_generate_unique_source_id(content: str = "", timestamp: float = None) -> str:
        if "procedural" in content:
            return "S_12345678_aaaaaaaa"
        return "S_12345679_bbbbbbbb"

    # Apply patches
    monkeypatch.setattr(FlaskRAGAssistantV2, "search_knowledge_base", fake_search)
    monkeypatch.setattr("rag_assistant_v2.generate_unique_source_id", fake_generate_unique_source_id)
    monkeypatch.setattr("rag_assistant_v2.OpenAIService.get_chat_response", fake_get_chat_response, raising=False)

    # Instantiate and call
    assistant = FlaskRAGAssistantV2()
    answer, cited_sources, _, _, _ = assistant.generate_rag_response("How do I perform the test procedure?")

    # Debug output
    print(f"answer: {answer}")
    print(f"cited_sources: {cited_sources}")

    # Assert citation mapping in answer and source objects
    assert "[1]" in answer and "[2]" in answer, "Answer should contain numeric display citations."
    ids = {s['id'] for s in cited_sources}
    display_ids = {s['display_id'] for s in cited_sources}
    assert "S_12345678_aaaaaaaa" in ids and "S_12345679_bbbbbbbb" in ids, "Should return both unique source ids."
    assert "1" in display_ids and "2" in display_ids, "Display IDs should be numeric."
    # Ensure that citation [1] maps to procedural and [2] to informational
    for src in cited_sources:
        if src['display_id'] == "1":
            assert src['id'] == "S_12345678_aaaaaaaa"
        if src['display_id'] == "2":
            assert src['id'] == "S_12345679_bbbbbbbb"
