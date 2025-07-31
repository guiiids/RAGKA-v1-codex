A detailed Project Change Request (PCR) to implement the proposed changes for a more intelligent and conversational RAG assistant.

-----

### **Project Change Request**

  * **Project:** Conversational RAG Assistant Improvement
  * **Change Request ID:** `PCR-20250716-01`
  * **Date:** July 16, 2025
  * **Title:** Implement Intelligent RAG Routing for Improved Conversational Memory

-----

### **1. Problem Statement**

The current RAG assistant implementation suffers from conversational memory failures. It performs a new knowledge base search and re-injects the full context on every conversational turn. This stateless approach causes several issues:

  * **Inconsistent Answers:** The assistant can contradict itself on follow-up questions because it re-evaluates new search results instead of recalling what it just said.
  * **Contextual Confusion:** By repeatedly providing the same source documents, we confuse the model and implicitly encourage it to ignore the conversational history.
  * **Inefficiency:** Unnecessary API calls are made to the search service on turns where the answer is already available in the chat history.

This leads to a poor user experience, as demonstrated by the "memory test" failures where the bot could not correctly recall numbered items from its own previous response.

-----

### **2. Proposed Change**

We will refactor the core RAG logic to move from a stateless `search-then-answer` model to an intelligent, stateful **"Router"** model. Before generating a response, the system will first classify the user's query intent and choose the most appropriate action, drastically reducing unnecessary searches and forcing the model to rely on its conversational memory.

The new workflow will be:

1.  **Classify Intent:** Determine if a query is a new topic, a follow-up that can be answered from history, or a follow-up that requires a more specific search.
2.  **Conditional Action:** Based on the intent, either:
      * **Answer from History:** Skip the search entirely.
      * **Rewrite & Search:** Use the conversation history to create a better search query, then search.
      * **Fresh Search:** Perform a standard search for a new topic.
3.  **Generate Response:** Call the LLM with the appropriate context (either new, rewritten, or none at all).

-----

### **3. Detailed Implementation Steps**

The following changes should be made within the `FlaskRAGAssistantV2` class and its related functions.

#### **Task 3.1: Enhance `detect_query_type` to Function as the "Router"**

The current `detect_query_type` function is a good starting point but must be expanded. It should classify queries into more specific categories.

**Location:** `detect_query_type` function.

**Action:**
Modify the function to identify and return one of the following query types:

  * `HISTORY_RECALL`: For questions like "What was my first question?"
  * `CONTEXTUAL_FOLLOW_UP`: For questions like "Tell me more about item 3" or "Elaborate on that."
  * `NEW_TOPIC_PROCEDURAL`: For new procedural questions.
  * `NEW_TOPIC_INFORMATIONAL`: For new informational questions.

**Example Code:**

```python
# In FlaskRAGAssistantV2 class
def detect_query_type(self, query: str, conversation_history: List[Dict] = None) -> str:
    """
    Detect the user's intent to route the query appropriately.
    """
    query_lower = query.lower()

    # 1. Check for direct history recall
    recall_patterns = [r'what (was|did) (i|we) (ask|say)', r'what was my first question']
    for pattern in recall_patterns:
        if re.search(pattern, query_lower):
            logger.info("Query detected as HISTORY_RECALL")
            return "HISTORY_RECALL"

    # 2. Check for contextual follow-ups that don't need a new search
    follow_up_patterns = [
        r'tell me more about (that|it|item|point|number|the last one)',
        r'elaborate on (that|it)',
        r'(what about|more details on) (item|point|number) \d+'
    ]
    for pattern in follow_up_patterns:
        if re.search(pattern, query_lower):
            logger.info("Query detected as CONTEXTUAL_FOLLOW_UP")
            return "CONTEXTUAL_FOLLOW_UP"

    # 3. If not a direct follow-up, use existing logic to classify as new topic
    # This part uses your existing procedural patterns
    procedural_patterns = [
        r'how (to|do|can|would|should) (i|we|you|one)?\s',
        r'what (is|are) the (steps|procedure|process)',
        # ... (keep your other procedural patterns)
    ]
    for pattern in procedural_patterns:
        if re.search(pattern, query_lower):
            logger.info("Query detected as NEW_TOPIC_PROCEDURAL")
            return "NEW_TOPIC_PROCEDURAL"
    
    logger.info("Query detected as NEW_TOPIC_INFORMATIONAL")
    return "NEW_TOPIC_INFORMATIONAL"
```

#### **Task 3.2: Refactor `generate_rag_response` to Use the Router**

The main `generate_rag_response` method must be rewritten to incorporate the new routing logic. It should decide whether to call `search_knowledge_base` based on the router's output.

**Location:** `generate_rag_response` method.

**Action:**
Restructure the method to follow the conditional logic. Only perform a knowledge base search when the query type is identified as a new topic. For follow-ups, rely on the existing `_cumulative_src_map` and the conversation history.

**Example Code:**

```python
# In FlaskRAGAssistantV2 class
def generate_rag_response(
    self, query: str, is_enhanced: bool = False
) -> Tuple[str, List[Dict], List[Dict], Dict[str, Any], str]:
    """
    Generate a response using the intelligent RAG router.
    """
    try:
        # Step 1: Classify the query's intent using the router
        history = self.conversation_manager.get_history()
        query_type = self.detect_query_type(query, history)

        context, src_map = "", {}

        # Step 2: Execute action based on intent
        if query_type in ["NEW_TOPIC_PROCEDURAL", "NEW_TOPIC_INFORMATIONAL"]:
            logger.info(f"Handling '{query_type}'. Performing a fresh knowledge base search.")
            kb_results = self.search_knowledge_base(query)
            if kb_results:
                context, src_map = self._prepare_context(kb_results)
                self._cumulative_src_map.update(src_map)
        
        elif query_type == "CONTEXTUAL_FOLLOW_UP" or query_type == "HISTORY_RECALL":
            logger.info(f"Handling '{query_type}'. Skipping search and using conversation history.")
            # No new context is needed. The model will use the chat history.
            # We use the cumulative map for citation filtering.
            src_map = self._cumulative_src_map
            context = "[No new context provided for this turn. Answer based on the conversation history.]"
        
        # This structure handles all cases. If no results are found, context remains empty.
        if not context:
             context = "[No relevant information found in the knowledge base.]"


        # Step 3: Generate the answer using chat (this part remains mostly the same)
        # Note: _chat_answer_with_history needs to correctly handle an empty 'context' string
        answer = self._chat_answer_with_history(query, context, src_map)

        # Step 4: Filter citations across all *seen* sources
        cited_raw = self._filter_cited(answer, self._cumulative_src_map)

        # ... (rest of the function: renumbering, evaluation, logging) remains the same
        # ...

    except Exception as exc:
        # ... (error handling remains the same)
```

-----

### **4. Test Plan & Validation**

To ensure the changes work as expected and are "bulletproof," a new unit test must be created. This test will simulate a multi-turn conversation and assert that the knowledge base search is only triggered when necessary.

**Action:** Add the following test function to the test suite.

```python
# You can save this as a new file, e.g., test_intelligent_rag_routing.py
import unittest
from unittest.mock import patch, MagicMock

# Assuming your main script is named 'rag_assistant_v2.py'
# and contains the FlaskRAGAssistantV2 class.
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
        
        self.assistant.generate_rag_response("Tell me more about the first one.")

        # Assert search call count is STILL 1
        self.assertEqual(self.mock_search.call_count, 1, "FAIL: Search should NOT be called for a direct follow-up.")
        print("PASS: Search was skipped for a direct follow-up.")

        # --- Turn 3: New Topic ---
        self.mock_search.return_value = [{"chunk": "CrossLab is different.", "title": "Doc2"}]
        self.mock_chat.return_value = "CrossLab is different [S2_...]."

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

        # --- Turn 2: History Recall Question ---
        self.mock_chat.return_value = "You asked 'What is feature 1?'"
        
        self.assistant.generate_rag_response("What was my first question?")

        # Assert search call count is STILL 1
        self.assertEqual(self.mock_search.call_count, 1, "FAIL: Search should NOT be called for a history recall question.")
        print("PASS: Search was skipped for a history recall question.")


# This allows you to run the tests directly from the command line
if __name__ == '__main__':
    unittest.main()
```

-----

### **5. Risks and Mitigation**

  * **Risk:** The `detect_query_type` router may misclassify a query.
  * **Mitigation:** The initial implementation relies on robust regular expressions. We will need to monitor logs for misclassifications and refine the patterns over time. The default fallback to "informational" is a safe one. For future enhancements, this regex-based router could be replaced with a more powerful LLM-based classifier.