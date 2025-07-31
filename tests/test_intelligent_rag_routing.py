"""
Test file for the intelligent RAG routing functionality in FlaskRAGAssistantV2.
"""
import unittest
from unittest.mock import patch, MagicMock
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Import the FlaskRAGAssistantV2 class
from rag_assistant_v2 import FlaskRAGAssistantV2

class TestIntelligentRAGRouting(unittest.TestCase):

    def setUp(self):
        """
        This method is called before each test function, ensuring a fresh
        instance and mocks for every test case.
        """
        self.assistant = FlaskRAGAssistantV2()
        
        # We patch the search and chat methods for the duration of the test
        self.patcher_search = patch.object(self.assistant, 'search_knowledge_base', new_callable=MagicMock)
        self.patcher_chat = patch.object(self.assistant, '_chat_answer_with_history', new_callable=MagicMock)
        
        self.mock_search = self.patcher_search.start()
        self.mock_chat = self.patcher_chat.start()

        # Add a cleanup step to stop the patchers after the test
        self.addCleanup(self.patcher_search.stop)
        self.addCleanup(self.patcher_chat.stop)


    def test_routing_with_standard_follow_up(self):
        """
        Tests the primary conversational flow with a standard follow-up.
        e.g., "Tell me more about the first one."
        """
        print("\nRunning test: Standard Follow-up")

        # --- Turn 1: New Topic ---
        self.mock_search.return_value = [{"chunk": "Feature 1 is API.", "title": "Doc1"}]
        self.mock_chat.return_value = "Feature 1 is API [S1_...]."
        
        self.assistant.generate_rag_response("What is feature 1?")
        
        # Assert search was called ONCE
        self.assertEqual(self.mock_search.call_count, 1, "FAIL: Search should be called for an initial query.")
        print("PASS: Search was called for the initial query.")

        # --- Turn 2: Contextual Follow-up ---
        self.mock_chat.return_value = "The API is great [S1_...]."
        
        # Add conversation history to the assistant
        self.assistant.conversation_manager.add_user_message("What is feature 1?")
        self.assistant.conversation_manager.add_assistant_message("Feature 1 is API [S1_...].")
        
        # Print conversation history for debugging
        print("Conversation history before follow-up:")
        for i, msg in enumerate(self.assistant.conversation_manager.get_history()):
            print(f"  {i}: {msg['role']} - {msg['content'][:50]}...")
        
        # Now try the follow-up
        self.assistant.generate_rag_response("Tell me more about the first one.")

        # Assert search call count is STILL 1
        self.assertEqual(self.mock_search.call_count, 1, "FAIL: Search should NOT be called for a direct follow-up.")
        print("PASS: Search was skipped for a direct follow-up.")

        # --- Turn 3: New Topic ---
        self.mock_search.return_value = [{"chunk": "CrossLab is different.", "title": "Doc2"}]
        self.mock_chat.return_value = "CrossLab is different [S2_...]."

        # Add conversation history for the new topic
        self.assistant.conversation_manager.add_user_message("Tell me more about the first one.")
        self.assistant.conversation_manager.add_assistant_message("The API is great [S1_...].")

        # Print conversation history for debugging
        print("\nConversation history before new topic:")
        for i, msg in enumerate(self.assistant.conversation_manager.get_history()):
            print(f"  {i}: {msg['role']} - {msg['content'][:50]}...")

        # Print the query type that's being detected
        query_type = self.assistant.detect_query_type("What about CrossLab?", self.assistant.conversation_manager.get_history())
        print(f"Query type detected for 'What about CrossLab?': {query_type}")

        self.assistant.generate_rag_response("What about CrossLab?")

        # Assert search call count is now 2
        self.assertEqual(self.mock_search.call_count, 2, "FAIL: Search should be called again for a new topic.")
        print("PASS: Search was called for a new topic.")


    def test_routing_with_varied_follow_up(self):
        """
        Tests the conversational flow with a different, but semantically
        similar, follow-up to ensure router consistency.
        e.g., "Elaborate on that."
        """
        print("\nRunning test: Varied Follow-up")

        # --- Turn 1: New Topic ---
        self.mock_search.return_value = [{"chunk": "Feature 1 is API.", "title": "Doc1"}]
        self.mock_chat.return_value = "Feature 1 is API [S1_...]."
        
        self.assistant.generate_rag_response("What is feature 1?")
        
        self.assertEqual(self.mock_search.call_count, 1)
        print("PASS: Search was called for the initial query.")

        # Add conversation history to the assistant
        self.assistant.conversation_manager.add_user_message("What is feature 1?")
        self.assistant.conversation_manager.add_assistant_message("Feature 1 is API [S1_...].")

        # Print conversation history for debugging
        print("Conversation history before follow-up:")
        for i, msg in enumerate(self.assistant.conversation_manager.get_history()):
            print(f"  {i}: {msg['role']} - {msg['content'][:50]}...")

        # --- Turn 2: Contextual Follow-up (different phrasing) ---
        self.mock_chat.return_value = "The API is great [S1_...]."
        
        self.assistant.generate_rag_response("Elaborate on that.") # <-- Different query

        # The core assertion: search is still NOT called.
        self.assertEqual(self.mock_search.call_count, 1, "FAIL: Search should NOT be called for a varied follow-up.")
        print("PASS: Search was skipped for a varied follow-up.")


    def test_routing_with_history_recall(self):
        """
        Tests that a direct recall question does not trigger a search.
        """
        print("\nRunning test: History Recall")

        # --- Turn 1: New Topic ---
        self.mock_search.return_value = [{"chunk": "Feature 1 is API.", "title": "Doc1"}]
        self.mock_chat.return_value = "Feature 1 is API [S1_...]."
        
        self.assistant.generate_rag_response("What is feature 1?")
        
        self.assertEqual(self.mock_search.call_count, 1)
        print("PASS: Search was called for the initial query.")

        # Add conversation history to the assistant
        self.assistant.conversation_manager.add_user_message("What is feature 1?")
        self.assistant.conversation_manager.add_assistant_message("Feature 1 is API [S1_...].")

        # Print conversation history for debugging
        print("Conversation history before follow-up:")
        for i, msg in enumerate(self.assistant.conversation_manager.get_history()):
            print(f"  {i}: {msg['role']} - {msg['content'][:50]}...")

        # --- Turn 2: History Recall Question ---
        self.mock_chat.return_value = "You asked 'What is feature 1?'"
        
        self.assistant.generate_rag_response("What was my first question?")

        # Assert search call count is STILL 1
        self.assertEqual(self.mock_search.call_count, 1, "FAIL: Search should NOT be called for a history recall question.")
        print("PASS: Search was skipped for a history recall question.")


# This allows you to run the tests directly from the command line
if __name__ == '__main__':
    unittest.main()
