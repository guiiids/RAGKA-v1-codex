"""
Simple RAG Assistant for RAGKA

This replaces the over-engineered rag_assistant_v2.py with a clean, simple approach
that relies on Redis conversation memory and GPT-4's natural understanding.
"""

import logging
import time
import json
from typing import Dict, List, Optional, Generator, Any
from datetime import datetime

from services.simple_conversation_manager import simple_conversation_manager
from services.simple_search_decision import SimpleSearchDecision
from openai_service import OpenAIService
from db_manager import DatabaseManager
import os
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class SimpleRAGAssistant:
    """
    Simple RAG assistant that replaces all complex entity detection and 
    classification logic with conversation memory and intelligent search decisions.
    
    This eliminates:
    - Entity detection
    - Pattern matching
    - Complex classification systems
    - Query mediation
    
    And replaces with:
    - Simple conversation history in Redis
    - GPT-4 deciding when to search
    - Natural context understanding
    """
    
    def __init__(self, session_id: str):
        load_dotenv()
        
        self.session_id = session_id
        self.conversation_manager = simple_conversation_manager
        self.db_manager = DatabaseManager()
        
        # Create OpenAI service instance
        self.openai_service = OpenAIService(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
            deployment_name=os.getenv("AZURE_OPENAI_MODEL")
        )
        
        # Create search decision service
        self.search_decision = SimpleSearchDecision(self.openai_service)
        
        # Source tracking for citations
        self._cumulative_src_map = {}
        self._current_message_sources = []
        
        logger.info(f"Simple RAG Assistant initialized for session {session_id}")
    
    def stream_rag_response(self, query: str) -> Generator[Dict[str, Any], None, None]:
        """
        Stream a RAG response using the simple approach.
        
        Args:
            query: User's query
            
        Yields:
            Response chunks with metadata
        """
        try:
            start_time = time.time()
            logger.info(f"Processing query: '{query}' for session: {self.session_id}")
            
            # Step 1: Get conversation context
            conversation_context = self.conversation_manager.build_context_prompt(self.session_id)
            
            # Step 2: Decide if search is needed
            search_decision = self.search_decision.needs_search(query, conversation_context)
            
            logger.info(f"Search decision: {search_decision['needs_search']} - {search_decision['reasoning']}")
            
            # Step 3: Build response based on decision
            if search_decision["needs_search"]:
                # Search + context approach
                yield from self._search_and_respond(
                    query, 
                    search_decision.get("search_query", query),
                    conversation_context
                )
            else:
                # Context-only approach
                yield from self._context_only_respond(query, conversation_context)
            
            # Step 4: Store the exchange (handled in the response methods)
            
            logger.info(f"Query processed in {time.time() - start_time:.2f}s")
            
        except Exception as e:
            logger.error(f"Error in stream_rag_response: {e}")
            yield {
                "type": "error",
                "content": f"I encountered an error processing your query: {str(e)}",
                "error": str(e)
            }
    
    def _search_and_respond(
        self, 
        original_query: str, 
        search_query: str,
        conversation_context: str
    ) -> Generator[Dict[str, Any], None, None]:
        """Handle queries that need knowledge base search."""
        try:
            # Perform vector search
            logger.info(f"Searching knowledge base for: '{search_query}'")
            search_results = self._search_knowledge_base(search_query)
            
            if not search_results:
                logger.warning("No search results found")
                yield {
                    "type": "content",
                    "content": "I couldn't find relevant information in the knowledge base. Could you rephrase your question or ask about something else?"
                }
                return
            
            # Prepare context with search results and conversation history
            context_with_search = self._build_search_context(
                search_results, 
                conversation_context
            )
            
            # Generate response with streaming
            full_response = ""
            for chunk in self._generate_streaming_response(
                original_query, 
                context_with_search,
                has_search_results=True
            ):
                if chunk["type"] == "content":
                    full_response += chunk["content"]
                yield chunk
            
            # Store the exchange
            self.conversation_manager.add_exchange(
                self.session_id,
                original_query,
                full_response
            )
            
            # Yield final metadata
            yield {
                "type": "metadata",
                "sources": self._current_message_sources,
                "search_performed": True,
                "search_query": search_query,
                "context_used": bool(conversation_context)
            }
            
        except Exception as e:
            logger.error(f"Error in search and respond: {e}")
            yield {
                "type": "error",
                "content": f"Error during search: {str(e)}"
            }
    
    def _context_only_respond(
        self, 
        query: str, 
        conversation_context: str
    ) -> Generator[Dict[str, Any], None, None]:
        """Handle queries that can be answered from context alone."""
        try:
            logger.info("Responding using conversation context only")
            
            # Generate response from context
            full_response = ""
            for chunk in self._generate_streaming_response(
                query, 
                conversation_context,
                has_search_results=False
            ):
                if chunk["type"] == "content":
                    full_response += chunk["content"]
                yield chunk
            
            # Store the exchange
            self.conversation_manager.add_exchange(
                self.session_id,
                query,
                full_response
            )
            
            # Yield final metadata
            yield {
                "type": "metadata",
                "sources": [],
                "search_performed": False,
                "context_used": True
            }
            
        except Exception as e:
            logger.error(f"Error in context-only response: {e}")
            yield {
                "type": "error",
                "content": f"Error generating response: {str(e)}"
            }
    
    def _search_knowledge_base(self, query: str) -> List[Dict]:
        """Search the knowledge base using vector search."""
        try:
            search_results = self.db_manager.search_vector_db(
                query=query,
                top_k=10,
                search_type="vector"
            )
            
            logger.info(f"Found {len(search_results)} search results")
            return search_results
            
        except Exception as e:
            logger.error(f"Error searching knowledge base: {e}")
            return []
    
    def _build_search_context(
        self, 
        search_results: List[Dict], 
        conversation_context: str
    ) -> str:
        """Build context combining search results and conversation history."""
        try:
            context_parts = []
            
            # Add conversation context if available
            if conversation_context:
                context_parts.append(conversation_context)
                context_parts.append("")  # Empty line separator
            
            # Add search results
            context_parts.append("Relevant information from knowledge base:")
            
            sources = []
            for i, result in enumerate(search_results[:5], 1):  # Top 5 results
                # Generate source ID
                source_id = f"S_{int(time.time() * 1000)}_{hash(result.get('chunk', ''))}"
                
                # Store source mapping
                source_info = {
                    "title": result.get("title", f"Document {i}"),
                    "parent_id": result.get("parent_id", ""),
                    "relevance": result.get("relevance_score", 0.0)
                }
                self._cumulative_src_map[source_id] = source_info
                sources.append(source_id)
                
                # Add to context
                context_parts.append(f'<source id="{source_id}">')
                context_parts.append(result.get("chunk", ""))
                context_parts.append("</source>")
            
            self._current_message_sources = sources
            
            return "\n".join(context_parts)
            
        except Exception as e:
            logger.error(f"Error building search context: {e}")
            return conversation_context or ""
    
    def _generate_streaming_response(
        self, 
        query: str, 
        context: str,
        has_search_results: bool
    ) -> Generator[Dict[str, Any], None, None]:
        """Generate streaming response using OpenAI."""
        try:
            # Build system prompt
            system_prompt = self._build_system_prompt(has_search_results)
            
            # Build user prompt
            if context:
                user_prompt = f"{context}\n\nUser query: {query}"
            else:
                user_prompt = query
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            # Get response from OpenAI (non-streaming for now)
            response = self.openai_service.get_chat_response(
                messages=messages,
                max_tokens=1000
            )
            
            # Yield as single chunk for now (can be made streaming later)
            yield {
                "type": "content",
                "content": response
            }
                
        except Exception as e:
            logger.error(f"Error generating streaming response: {e}")
            yield {
                "type": "error",
                "content": f"Error generating response: {str(e)}"
            }
    
    def _build_system_prompt(self, has_search_results: bool) -> str:
        """Build system prompt based on whether we have search results."""
        base_prompt = """You are a helpful AI assistant. Provide accurate, relevant responses to user queries."""
        
        if has_search_results:
            return base_prompt + """

When using information from the knowledge base sources:
- Include inline citations like [1], [2], etc.
- Use the source id numbers provided in the context
- Be accurate and cite sources appropriately
- If you reference information from previous conversation, mention that as well"""
        else:
            return base_prompt + """

You are responding based on the conversation context. Reference previous parts of the conversation naturally when relevant."""
    
    def get_session_summary(self) -> Dict:
        """Get summary of the current session."""
        return self.conversation_manager.get_session_summary(self.session_id)
    
    def clear_session(self) -> None:
        """Clear the session data."""
        self.conversation_manager.clear_session(self.session_id)
        self._cumulative_src_map = {}
        self._current_message_sources = []
        logger.info(f"Cleared session: {self.session_id}")


# Factory function for Flask integration
def create_simple_rag_assistant(session_id: str) -> SimpleRAGAssistant:
    """Create a simple RAG assistant instance."""
    return SimpleRAGAssistant(session_id)


# Test function
def test_simple_rag_assistant():
    """Test the simple RAG assistant."""
    assistant = SimpleRAGAssistant("test_session")
    
    # Clear any existing session
    assistant.clear_session()
    
    # Test queries
    test_queries = [
        "What is iLab?",
        "Is it the same as OpenLab?",
        "How do I use it?"
    ]
    
    for query in test_queries:
        print(f"\n{'='*50}")
        print(f"Query: {query}")
        print('='*50)
        
        response_parts = []
        for chunk in assistant.stream_rag_response(query):
            if chunk["type"] == "content":
                response_parts.append(chunk["content"])
                print(chunk["content"], end="", flush=True)
            elif chunk["type"] == "metadata":
                print(f"\n\nMetadata:")
                print(f"  Search performed: {chunk.get('search_performed', False)}")
                print(f"  Sources: {len(chunk.get('sources', []))}")
                print(f"  Context used: {chunk.get('context_used', False)}")
            elif chunk["type"] == "error":
                print(f"\nError: {chunk['content']}")
        
        print("\n")
    
    # Show session summary
    summary = assistant.get_session_summary()
    print(f"\nSession Summary: {summary}")


if __name__ == "__main__":
    test_simple_rag_assistant()
