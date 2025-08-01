import os
import re
import sys
import types

# Set minimal environment variables expected by the assistant before importing it
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://example.com")
os.environ.setdefault("AZURE_OPENAI_KEY", "test_key")
os.environ.setdefault("AZURE_OPENAI_API_VERSION", "2024-02-01")
os.environ.setdefault("CHAT_DEPLOYMENT_GPT4o", "test-deployment")
os.environ.setdefault("EMBEDDING_DEPLOYMENT", "test-embedding")
os.environ.setdefault("AZURE_SEARCH_SERVICE", "example-search")
os.environ.setdefault("AZURE_SEARCH_INDEX", "test-index")
os.environ.setdefault("AZURE_SEARCH_KEY", "test-key")
os.environ.setdefault("VECTOR_FIELD", "test-vector")

# Stub out database module to avoid heavy dependencies during import
sys.modules.setdefault("db_manager", types.SimpleNamespace(DatabaseManager=object))

from rag_assistant_simple_redis import EnhancedSimpleRedisRAGAssistant


class DummyMemory:
    def store_turn(self, session_id, user_msg, bot_msg, summary=None):
        pass

    def get_history(self, session_id, last_n_turns=10):
        return []

    def clear(self, session_id):
        pass


def test_citation_link_generation():
    assistant = EnhancedSimpleRedisRAGAssistant(session_id="test", memory=DummyMemory())
    result = assistant._convert_citations_to_links("Example [1] citation", [], "msg1")

    assert result.count("<a") == 1
    assert result.count("</a>") == 1
    assert re.search(r"<a[^>]*><a", result) is None
