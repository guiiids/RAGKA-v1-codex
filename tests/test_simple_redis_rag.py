"""
Minimal test harness for the pure-context, Redis-backed RAG assistant.
Allows for local manual test with a fixed session ID.
"""

from rag_assistant_simple_redis import EnhancedSimpleRedisRAGAssistant

if __name__ == "__main__":
    # Use a fixed session for demonstration
    session_id = "localtest"
    assistant = EnhancedSimpleRedisRAGAssistant(session_id=session_id)
    print("Welcome to the advanced Redis-backed RAG assistant demo.")
    print("Type a question. Type 'exit' to quit.")

    while True:
        userq = input("\nUser: ").strip()
        if not userq or userq.lower() == "exit":
            break
        answer = assistant.generate_response(userq)
        print("\nAssistant:", answer)
