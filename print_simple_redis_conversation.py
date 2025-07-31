"""
Prints the full conversation history for the 'localtest' session in the simplified Redis-backed RAG assistant.
Shows what Q&A context is available from memory_service that would be sent to the model.
"""

from services.simple_redis_memory import memory_service

if __name__ == "__main__":
    session_id = "localtest"
    last_n = 10  # change as needed
    history = memory_service.get_history(session_id, last_n_turns=last_n)
    print(f"Conversation for session '{session_id}':")
    if not history:
        print("(No conversation turns found in Redis.)")
    else:
        for i, (user, assistant) in enumerate(history, 1):
            print(f"\nTurn {i}:")
            print(f"  User: {user}")
            print(f"  Assistant: {assistant}")
