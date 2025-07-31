import re
from rag_assistant_simple_redis import EnhancedSimpleRedisRAGAssistant


def _count_anchors(text: str) -> int:
    return len(re.findall(r'<a[^>]+session-citation-link', text))


def test_convert_citations_idempotent():
    assistant = EnhancedSimpleRedisRAGAssistant.__new__(EnhancedSimpleRedisRAGAssistant)
    raw = "Example [1] more [2]."
    first = assistant._convert_citations_to_links(raw, [], "m")
    second = assistant._convert_citations_to_links(first, [], "m")
    assert first == second
    assert _count_anchors(second) == 2
