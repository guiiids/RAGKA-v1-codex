"""
Tests for the intelligent routing system.
"""
import pytest
from rag_assistant_v2 import FlaskRAGAssistantV2
from enhanced_pattern_matcher import EnhancedPatternMatcher
from conversation_context_analyzer import ConversationContextAnalyzer
from routing_logger import RoutingDecisionLogger

def test_pattern_matcher():
    """Test the enhanced pattern matcher."""
    matcher = EnhancedPatternMatcher()
    
    # Test procedural queries
    procedural_queries = [
        "How to create a calendar?",
        "What are the steps to configure permissions?",
        "Guide me through the setup process",
        "Show me how to add users"
    ]
    
    for query in procedural_queries:
        query_type, confidence = matcher.classify_query(query)
        assert query_type == "NEW_TOPIC_PROCEDURAL"
        assert confidence >= 0.7, f"Low confidence ({confidence}) for procedural query: {query}"
    
    # Test informational queries
    informational_queries = [
        "What is a calendar?",
        "Tell me about user permissions",
        "When was this feature added?",
        "Why do we need this?"
    ]
    
    for query in informational_queries:
        query_type, confidence = matcher.classify_query(query)
        assert query_type == "NEW_TOPIC_INFORMATIONAL"
        assert confidence >= 0.7, f"Low confidence ({confidence}) for informational query: {query}"
    
    # Test follow-up queries with context
    conversation_history = [
        {"role": "user", "content": "How do I create a calendar?"},
        {"role": "assistant", "content": "Here are the steps:\n1. Go to Settings\n2. Click 'Add Calendar'"}
    ]
    
    follow_up_queries = [
        "What's next?",
        "Tell me more about that",
        "Can you elaborate?",
        "What about step 2?"
    ]
    
    for query in follow_up_queries:
        query_type, confidence = matcher.classify_query(query, conversation_history)
        assert query_type == "CONTEXTUAL_FOLLOW_UP"
        assert confidence >= 0.6, f"Low confidence ({confidence}) for follow-up query: {query}"

def test_context_analyzer():
    """Test the conversation context analyzer."""
    analyzer = ConversationContextAnalyzer()
    
    # Test with no history
    query = "How do I create a calendar?"
    scores = analyzer.analyze_context(query)
    assert scores["NEW_TOPIC_PROCEDURAL"] > scores["CONTEXTUAL_FOLLOW_UP"]
    
    # Test with conversation history
    history = [
        {"role": "user", "content": "How do I create a calendar?"},
        {"role": "assistant", "content": "Here are the steps:\n1. Go to Settings\n2. Click 'Add Calendar'"},
        {"role": "user", "content": "What's next?"}
    ]
    
    scores = analyzer.analyze_context("Tell me more", history)
    assert scores["CONTEXTUAL_FOLLOW_UP"] > scores["NEW_TOPIC_INFORMATIONAL"]
    
    # Test temporal references
    scores = analyzer.analyze_context("What did we discuss earlier?", history)
    assert scores["HISTORY_RECALL"] > scores["NEW_TOPIC_INFORMATIONAL"]
    
    # Test explanation generation
    explanation = analyzer.get_context_explanation("What's next?", history)
    assert len(explanation) > 0
    assert any("short" in line.lower() for line in explanation)

def test_routing_logger():
    """Test the routing decision logger."""
    logger = RoutingDecisionLogger()
    
    # Test logging a decision
    logger.log_decision(
        query="How to create a calendar?",
        detected_type="NEW_TOPIC_PROCEDURAL",
        confidence=0.85,
        search_performed=True,
        conversation_context=[],
        pattern_matches={"exact": True, "fuzzy": False},
        processing_time_ms=45.5
    )
    
    # Test analyzing recent decisions
    analysis = logger.analyze_recent_decisions(hours=24)
    assert analysis["total_decisions"] > 0
    assert "NEW_TOPIC_PROCEDURAL" in analysis["type_distribution"]
    
    # Test summary stats
    stats = logger.get_summary_stats()
    assert stats["total_decisions"] > 0
    assert "by_type" in stats
    assert "by_confidence" in stats

def test_integrated_routing():
    """Test the integrated routing system."""
    assistant = FlaskRAGAssistantV2()
    
    # Test new topic detection
    query = "How do I create a calendar?"
    query_type = assistant.detect_query_type(query)
    assert query_type == "NEW_TOPIC_PROCEDURAL"
    
    # Add some conversation history
    assistant.conversation_manager.add_user_message(query)
    assistant.conversation_manager.add_assistant_message(
        "Here are the steps to create a calendar:\n1. Go to Settings\n2. Click 'Add Calendar'"
    )
    
    # Test follow-up detection
    follow_up = "What's next after that?"
    query_type = assistant.detect_query_type(
        follow_up,
        assistant.conversation_manager.get_history()
    )
    assert query_type == "CONTEXTUAL_FOLLOW_UP"
    
    # Test history recall
    history_query = "What did we discuss earlier?"
    query_type = assistant.detect_query_type(
        history_query,
        assistant.conversation_manager.get_history()
    )
    assert query_type == "HISTORY_RECALL"

def test_edge_cases():
    """Test edge cases and boundary conditions."""
    matcher = EnhancedPatternMatcher()
    analyzer = ConversationContextAnalyzer()
    
    # Test empty query
    query_type, confidence = matcher.classify_query("")
    assert query_type == "NEW_TOPIC_INFORMATIONAL"
    assert confidence == 0.0
    
    # Test very short queries
    short_queries = ["?", "help", "next"]
    for query in short_queries:
        scores = analyzer.analyze_context(query)
        assert scores["CONTEXTUAL_FOLLOW_UP"] > 0.0
    
    # Test queries with mixed signals
    mixed_query = "What about creating a new calendar instead?"
    scores = analyzer.analyze_context(mixed_query)
    assert scores["NEW_TOPIC_PROCEDURAL"] > 0.0
    assert scores["CONTEXTUAL_FOLLOW_UP"] > 0.0
    
    # Test with empty history
    query_type, confidence = matcher.classify_query(
        "Tell me more about that",
        conversation_history=[]
    )
    assert confidence < 0.7  # Should have low confidence without context

def test_performance():
    """Test performance and response times."""
    matcher = EnhancedPatternMatcher()
    analyzer = ConversationContextAnalyzer()
    
    # Prepare a large conversation history
    history = []
    for i in range(10):
        history.extend([
            {"role": "user", "content": f"Question {i}"},
            {"role": "assistant", "content": f"Answer {i}"}
        ])
    
    # Test pattern matcher performance
    import time
    start = time.time()
    for _ in range(100):
        matcher.classify_query("How do I create a calendar?", history)
    pattern_time = (time.time() - start) / 100
    assert pattern_time < 0.01  # Should take less than 10ms per query
    
    # Test context analyzer performance
    start = time.time()
    for _ in range(100):
        analyzer.analyze_context("What's next?", history)
    context_time = (time.time() - start) / 100
    assert context_time < 0.01  # Should take less than 10ms per analysis

if __name__ == "__main__":
    pytest.main([__file__])
