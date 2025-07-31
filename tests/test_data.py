"""
Test data for GPT-4 intent classifier tests.
"""

# Test queries with expected confidence scores
TEST_QUERIES = {
    "informational": [
        ("What is a calendar?", 0.9),
        ("Tell me about user permissions", 0.9),
        ("When was this feature added?", 0.9),
        ("Why do we need this?", 0.9),
        ("Explain the dashboard", 0.9)
    ],
    "procedural": [
        ("How to create a calendar?", 0.9),
        ("What are the steps to configure permissions?", 0.9),
        ("Guide me through the setup process", 0.9),
        ("Show me how to add users", 0.9),
        ("Steps to export data", 0.9)
    ],
    "followup": [
        ("What's next?", 0.8),
        ("Tell me more about that", 0.8),
        ("Can you elaborate?", 0.8),
        ("What about step 2?", 0.8),
        ("And then?", 0.8)
    ],
    "history": [
        ("What was my first question?", 0.9),
        ("What did we discuss earlier?", 0.9),
        ("Can you summarize our conversation?", 0.9),
        ("What did you tell me about calendars?", 0.9),
        ("Go back to what you said before", 0.9)
    ],
    "edge_cases": [
        ("?", 0.6),
        ("help", 0.6),
        ("next", 0.6),
        ("yes", 0.6),
        ("no", 0.6)
    ]
}

# Test conversation histories
TEST_CONVERSATIONS = {
    "calendar_setup": [
        {"role": "user", "content": "How do I create a calendar?"},
        {"role": "assistant", "content": "Here are the steps:\n1. Go to Settings\n2. Click 'Add Calendar'\n3. Enter calendar details\n4. Click Save"}
    ],
    "permission_discussion": [
        {"role": "user", "content": "What are user permissions?"},
        {"role": "assistant", "content": "User permissions control what actions each user can perform in the system."},
        {"role": "user", "content": "How do I change them?"},
        {"role": "assistant", "content": "You can modify permissions in the admin panel."}
    ],
    "feature_explanation": [
        {"role": "user", "content": "Tell me about the new dashboard"},
        {"role": "assistant", "content": "The dashboard shows key metrics and analytics."},
        {"role": "user", "content": "What metrics specifically?"},
        {"role": "assistant", "content": "It displays user activity, system usage, and performance data."}
    ]
}

# Mock API responses for testing
MOCK_RESPONSES = {
    # Informational queries
    "What is a calendar?": ("NEW_TOPIC_INFORMATIONAL", 0.9),
    "Tell me about user permissions": ("NEW_TOPIC_INFORMATIONAL", 0.9),
    
    # Procedural queries
    "How to create a calendar?": ("NEW_TOPIC_PROCEDURAL", 0.9),
    "What are the steps to configure permissions?": ("NEW_TOPIC_PROCEDURAL", 0.9),
    
    # Follow-up queries
    "Tell me more": ("CONTEXTUAL_FOLLOW_UP", 0.8),
    "What's next?": ("CONTEXTUAL_FOLLOW_UP", 0.8),
    
    # History recall queries
    "What did we discuss?": ("HISTORY_RECALL", 0.9),
    "What was my first question?": ("HISTORY_RECALL", 0.9),
    
    # Edge cases
    "?": ("CONTEXTUAL_FOLLOW_UP", 0.6),
    "help": ("CONTEXTUAL_FOLLOW_UP", 0.6),
    "": ("NEW_TOPIC_INFORMATIONAL", 0.5)
}
