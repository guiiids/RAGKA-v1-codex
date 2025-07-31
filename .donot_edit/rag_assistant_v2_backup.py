"""
Improved version of the RAG assistant with better handling of procedural content
"""
import logging
from typing import List, Dict, Tuple, Optional, Any, Generator, Union
import traceback
from openai import AzureOpenAI
from services.redis_service import redis_service
import json
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from azure.core.credentials import AzureKeyCredential
import re
import sys
import os
import json
import time
import hashlib
from openai_logger import log_openai_call
from db_manager import DatabaseManager
from conversation_manager import ConversationManager
from openai_service import OpenAIService
from rag_improvement_logging import get_phase_logger, get_checkpoint_logger, get_test_logger, get_compare_logger
from enhanced_pattern_matcher import EnhancedPatternMatcher
from conversation_context_analyzer import ConversationContextAnalyzer
from routing_logger import RoutingDecisionLogger
from query_mediator import QueryMediator

# Import config but handle the case where it might import streamlit
try:
    from config import (
        AZURE_OPENAI_ENDPOINT as OPENAI_ENDPOINT,
        AZURE_OPENAI_KEY as OPENAI_KEY,
        AZURE_OPENAI_API_VERSION as OPENAI_API_VERSION,
        AZURE_OPENAI_API_VERSION_O4_MINI as OPENAI_API_VERSION_O4_MINI,
        EMBEDDING_DEPLOYMENT,
        CHAT_DEPLOYMENT_GPT4o as CHAT_DEPLOYMENT,
        CHAT_DEPLOYMENT_O4_MINI,
        AZURE_SEARCH_SERVICE as SEARCH_ENDPOINT,
        AZURE_SEARCH_INDEX as SEARCH_INDEX,
        AZURE_SEARCH_KEY as SEARCH_KEY,
        VECTOR_FIELD,
    )
except ImportError as e:
    if 'streamlit' in str(e):
        # Define fallback values or load from environment
        OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT")
        OPENAI_KEY = os.environ.get("AZURE_OPENAI_KEY")
        OPENAI_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION")
        OPENAI_API_VERSION_O4_MINI = os.environ.get("AZURE_OPENAI_API_VERSION_O4_MINI")
        EMBEDDING_DEPLOYMENT = os.environ.get("EMBEDDING_DEPLOYMENT")
        CHAT_DEPLOYMENT = os.environ.get("CHAT_DEPLOYMENT_GPT4o")
        CHAT_DEPLOYMENT_O4_MINI = os.environ.get("CHAT_DEPLOYMENT_O4_MINI")
        SEARCH_ENDPOINT = os.environ.get("AZURE_SEARCH_SERVICE")
        SEARCH_INDEX = os.environ.get("AZURE_SEARCH_INDEX")
        SEARCH_KEY = os.environ.get("AZURE_SEARCH_KEY")
        VECTOR_FIELD = os.environ.get("VECTOR_FIELD")
    else:
        raise

# Set up phase-specific logger
logger = get_phase_logger(3)  # Updated to Phase 3
checkpoint_logger = get_checkpoint_logger(3)  # Updated to Phase 3
test_logger = get_test_logger()
compare_logger = get_compare_logger()


class FactCheckerStub:
    """No-op evaluator so we still return a dict in the tuple."""
    def evaluate_response(
        self, query: str, answer: str, context: str, deployment: str
    ) -> Dict[str, Any]:
        return {}


# ─────────── Phase 1: Improved Chunking Strategy ───────────

def chunk_document(text: str, max_chunk_size: int = 1000) -> List[str]:
    """
    Chunk document by semantic boundaries like headers and sections.
    
    Args:
        text: The document text to chunk
        max_chunk_size: Maximum size of each chunk in characters
        
    Returns:
        List of chunks that preserve semantic structure
    """
    logger.info(f"Chunking document of length {len(text)} with max chunk size {max_chunk_size}")
    
    # If the document is small enough, return it as a single chunk
    if len(text) <= max_chunk_size:
        logger.info(f"Document is smaller than max chunk size, returning as single chunk")
        return [text]
    
    # Split by section headers (e.g., lines starting with # or ## in markdown, or lines ending with a colon)
    sections = re.split(r'((?:^|\n)(?:#+\s+[^\n]+|\d+\.\s+[^\n]+|[A-Z][^\n:]{5,40}:))', text, flags=re.MULTILINE)
    
    chunks = []
    current_chunk = ""
    current_headers = []
    
    for i, section in enumerate(sections):
        # Skip empty sections
        if not section.strip():
            continue
            
        # If this is a header or start of a numbered step
        if re.match(r'(?:^|\n)(?:#+\s+[^\n]+|\d+\.\s+[^\n]+|[A-Z][^\n:]{5,40}:)', section, flags=re.MULTILINE):
            current_headers.append(section.strip())
            logger.debug(f"Found header: {section.strip()}")
        # If this is content
        elif i > 0:
            # If adding this section would exceed max size, save current chunk and start new one
            if len(current_chunk) + len(section) > max_chunk_size:
                # Include headers in chunk for context
                full_chunk = " ".join(current_headers) + " " + current_chunk
                chunks.append(full_chunk)
                logger.debug(f"Created chunk of length {len(full_chunk)}")
                current_chunk = section
            else:
                current_chunk += section
    
    # Add the last chunk if not empty
    if current_chunk:
        full_chunk = " ".join(current_headers) + " " + current_chunk
        chunks.append(full_chunk)
        logger.debug(f"Created final chunk of length {len(full_chunk)}")
    
    # If no chunks were created (which can happen if the regex didn't match anything),
    # just split the document by size
    if not chunks:
        logger.warning("No semantic boundaries found, splitting by size")
        for i in range(0, len(text), max_chunk_size):
            chunks.append(text[i:i + max_chunk_size])
    
    logger.info(f"Document chunked into {len(chunks)} chunks")
    return chunks


def extract_metadata(chunk: str) -> Dict[str, Any]:
    """
    Extract metadata from chunks to improve retrieval and context.
    
    Args:
        chunk: The text chunk to analyze
        
    Returns:
        Dictionary of metadata about the chunk
    """
    metadata = {}
    
    # Detect if chunk contains procedural content (numbered steps)
    metadata["is_procedural"] = bool(re.search(r'\d+\.\s+', chunk))
    
    # Extract section level/hierarchy
    if re.search(r'^#+\s+', chunk):
        # Markdown heading level
        heading_match = re.search(r'^(#+)\s+', chunk)
        metadata["section_level"] = len(heading_match.group(1)) if heading_match else 0
    
    # Extract any step numbers
    step_numbers = re.findall(r'(\d+)\.\s+', chunk)
    if step_numbers:
        metadata["steps"] = [int(num) for num in step_numbers]
        metadata["first_step"] = min(metadata["steps"])
        metadata["last_step"] = max(metadata["steps"])
    
    # Detect if this is the start of a procedure
    metadata["is_procedure_start"] = bool(
        re.search(r'(?:how to|steps to|procedure for|guide to)', chunk.lower()) and
        metadata.get("is_procedural", False)
    )
    
    logger.debug(f"Extracted metadata: {metadata}")
    return metadata


def retrieve_with_hierarchy(results: List[Dict]) -> List[Dict]:
    """
    Reorganize search results to preserve document hierarchy.
    
    Args:
        results: Original search results
        
    Returns:
        Reorganized results that preserve parent document structure
    """
    logger.info(f"Reorganizing {len(results)} results to preserve hierarchy")
    
    # Extract parent documents and their scores
    parent_docs = {}
    for result in results:
        parent_id = result.get("parent_id", "")
        if parent_id and parent_id not in parent_docs:
            parent_docs[parent_id] = result.get("relevance", 0.0)
    
    # For top parent documents, retrieve all their chunks in order
    ordered_results = []
    for parent_id, score in sorted(parent_docs.items(), key=lambda x: x[1], reverse=True)[:3]:
        # Get all chunks from this parent
        parent_chunks = [r for r in results if r.get("parent_id", "") == parent_id]
        
        # Add metadata to each chunk
        for chunk in parent_chunks:
            chunk["metadata"] = extract_metadata(chunk.get("chunk", ""))
        
        # Sort chunks by their position in the original document
        # This is a simplified approach - ideally we would have position information
        ordered_results.extend(parent_chunks)
        logger.debug(f"Added {len(parent_chunks)} chunks from parent {parent_id}")
    
    # If we couldn't organize by parent, just return the original results
    if not ordered_results:
        logger.warning("Could not organize by parent document, returning original results")
        return results
    
    logger.info(f"Reorganized into {len(ordered_results)} ordered results")
    return ordered_results


# ─────────── Phase 2: Context Preparation Enhancements ───────────

def prioritize_procedural_content(results: List[Dict]) -> List[Dict]:
    """
    Reorder search results to prioritize procedural content.
    
    Args:
        results: Original search results
        
    Returns:
        Reordered results with procedural content first
    """
    logger.info(f"Prioritizing procedural content in {len(results)} results")
    
    # Add metadata to each result if not already present
    for result in results:
        if "metadata" not in result:
            result["metadata"] = extract_metadata(result.get("chunk", ""))
    
    # Separate procedural and non-procedural content
    procedural_results = []
    informational_results = []
    
    for result in results:
        if result.get("metadata", {}).get("is_procedural", False):
            procedural_results.append(result)
            logger.debug(f"Found procedural content: {result.get('chunk', '')[:50]}...")
        else:
            informational_results.append(result)
    
    # Log the counts
    logger.info(f"Found {len(procedural_results)} procedural and {len(informational_results)} informational results")
    
    # Sort procedural results by step order if possible
    # This ensures that steps appear in the correct sequence
    procedural_results.sort(
        key=lambda x: x.get("metadata", {}).get("first_step", 999),
        reverse=False
    )
    
    # Combine the results with procedural content first
    prioritized_results = procedural_results + informational_results
    
    return prioritized_results


def format_context_text(text: str) -> str:
    """
    Format context text to preserve structure.
    
    Args:
        text: The text to format
        
    Returns:
        Formatted text with preserved structure
    """
    # Add line breaks after long sentences
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    formatted = "\n\n".join(sentence for sentence in sentences if sentence)
    
    # Emphasize headings or keywords
    formatted = re.sub(r'(?<=\n\n)([A-Z][^\n:]{5,40})(?=\n\n)', r'**\1**', formatted)  # crude title detection
    
    # Preserve numbered steps
    formatted = re.sub(r'(\d+\.\s+)', r'\n\1', formatted)
    
    return formatted


def format_procedural_context(text: str) -> str:
    """
    Format procedural content to preserve steps and hierarchy.
    
    Args:
        text: The text to format
        
    Returns:
        Formatted text with preserved procedural structure
    """
    # Identify numbered steps or bullet points
    text = re.sub(r'(\d+\.\s+)', r'\n\1', text)
    text = re.sub(r'(\•\s+)', r'\n\1', text)
    
    # Emphasize section headers
    text = re.sub(r'([A-Z][^\n:]{5,40}:)', r'\n**\1**\n', text)
    
    # Preserve paragraph structure
    paragraphs = text.split('\n\n')
    formatted = "\n\n".join(p.strip() for p in paragraphs if p.strip())
    
    return formatted


def is_procedural_content(text: str) -> bool:
    """
    Detect if text contains procedural content like steps.
    
    Args:
        text: The text to analyze
        
    Returns:
        True if the text contains procedural content, False otherwise
    """
    # Check for numbered steps (e.g., "1. Do this")
    if re.search(r'\d+\.\s+[A-Z]', text):
        return True
    
    # Check for instructional keywords
    instructional_keywords = ['follow', 'steps', 'procedure', 'instructions', 'guide']
    if any(keyword in text.lower() for keyword in instructional_keywords):
        return True
        
    return False
def test_internal_citation_detection():
    """Test detection of internal citation IDs in answers."""
    test_logger.info("Running test_internal_citation_detection")
    assistant = FlaskRAGAssistantV2()
    # Prepare a fake src_map with internal ID
    src_map = {
        "S1_ab12cd34": {
            "title": "Test",
            "content": "Test content",
            "parent_id": "",
            "is_procedural": False
        }
    }
    answer = "Reference to source [S1_ab12cd34]."
    cited = assistant._filter_cited(answer, src_map)
    assert len(cited) == 1, "Should detect the internal citation"
    assert cited[0]["id"] == "S1_ab12cd34", "Detected ID should match the internal citation"
    test_logger.info("test_internal_citation_detection passed")
    return True
    
    # Check for instructional keywords
    instructional_keywords = ['follow', 'steps', 'procedure', 'instructions', 'guide']
    if any(keyword in text.lower() for keyword in instructional_keywords):
        return True
        
    return False


def generate_unique_source_id(content: str = "", timestamp: float = None) -> str:
    """
    Generate a unique, persistent ID for a source that remains stable across conversations.
    
    Args:
        content: The source content to hash (optional)
        timestamp: Optional timestamp, uses current time if not provided
        
    Returns:
        A unique ID in format: S_{timestamp}_{hash}
    """
    if timestamp is None:
        timestamp = int(time.time() * 1000)  # milliseconds for better uniqueness
    
    # Create a hash from content and timestamp for uniqueness
    hash_input = f"{content}_{timestamp}".encode('utf-8')
    content_hash = hashlib.md5(hash_input).hexdigest()[:8]  # First 8 chars for brevity
    
    unique_id = f"S_{timestamp}_{content_hash}"
    logger.debug(f"Generated unique source ID: {unique_id}")
    return unique_id


class FlaskRAGAssistantV2:
    """Retrieval-Augmented Generation assistant that maintains conversation
    history, summarizes older turns when needed, and provides improved
    handling of procedural content."""

    def __init__(self, settings=None, session_id=None) -> None:
        self._init_cfg()
        
        # Persistent session-global citation list and lookup:
        self._display_ordered_citations = []  # Ordered list of unique source IDs, stable across session
        self._display_ordered_citation_map = {}  # unique_id -> source info dict for fast lookup

        # Message-scoped citation system
        self._message_counter = 0
        self._message_source_maps = {}  # message_id -> source_map
        self._all_sources = {}  # uid -> source_info (for lookups)

        # Store session id for Redis-backed persistence
        self.session_id = session_id

        # Initialize the OpenAI service
        self.openai_service = OpenAIService(
            azure_endpoint=self.openai_endpoint,
            api_key=self.openai_key,
            api_version=self.openai_api_version or "2023-05-15",
            deployment_name=self.deployment_name
        )
        
        # Initialize enhanced components
        self.pattern_matcher = EnhancedPatternMatcher()
        self.context_analyzer = ConversationContextAnalyzer()
        self.routing_logger = RoutingDecisionLogger()
        
        # Initialize the query mediator with enhanced threshold for better entity detection
        self.query_mediator = QueryMediator(self.openai_service, confidence_threshold=0.6)
        
        # Initialize the conversation manager with the system prompt
        self.conversation_manager = ConversationManager(self.DEFAULT_SYSTEM_PROMPT)
        
        # For backward compatibility
        self.openai_client = AzureOpenAI(
            azure_endpoint=self.openai_endpoint,
            api_key=self.openai_key,
            api_version=self.openai_api_version or "2023-05-15",
        )
        
        self.fact_checker = FactCheckerStub()
        
        # Model parameters with defaults
        self.temperature = 0.3
        self.top_p = 1.0
        self.max_completion_tokens = 1000
        self.presence_penalty = 0.6
        self.frequency_penalty = 0.6

        # Conversation history window size (in turns)
        self.max_history_turns = 5

        # Flag to track if history was trimmed in the most recent request
        self._history_trimmed = False

        # Summarization settings
        self.summarization_settings = {
            "enabled": True,
            "max_summary_tokens": 800,
            "summary_temperature": 0.3,
        }
        
        # Load settings if provided
        self.settings = settings or {}
        self._load_settings()
        
        logger.info("FlaskRAGAssistantV2 initialized with conversation history")
        self._cumulative_src_map = {}

        if self.session_id:
            self._load_citation_map_from_redis()

    def _save_citation_map_to_redis(self):
        if self.session_id:
            try:
                serialized = json.dumps(self._display_ordered_citation_map)
                redis_service.set(f"citationmap:{self.session_id}", serialized)
            except Exception as e:
                logger.error(f"Failed to save citation map to Redis: {e}")

    def _load_citation_map_from_redis(self):
        if self.session_id:
            try:
                data = redis_service.get(f"citationmap:{self.session_id}")
                if data:
                    # Py-redis may return bytes
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")
                    self._display_ordered_citation_map = json.loads(data)
                    logger.info(f"Loaded citation map from Redis for session {self.session_id}, entries: {len(self._display_ordered_citation_map)}")
                else:
                    self._display_ordered_citation_map = {}
            except Exception as e:
                logger.error(f"Failed to load citation map from Redis: {e}")

    def _rebuild_citation_map(self, cited_sources):
        """
        Ensures self._display_ordered_citations and self._display_ordered_citation_map
        are updated per request, not just at object init. Run after generating cited_sources.

        IMPORTANT: ALL unique sources from the entire session will be preserved for lookup,
        so past hyperlinks in prior messages always remain resolvable.
        Every turn, logs will show both: (a) the full set of preserved sources (all_source_ids) and
        (b) the newly cited sources for the current message (current_ids).
        """
        # Preserve ALL sources from ALL previous and current messages for lookup
        # Only append new unique sources, do not remove any
        self._display_ordered_citations = []
        for source in cited_sources:
            uid = source.get("id")
            if uid:
                self._display_ordered_citations.append(uid)
                # If new, add to preserved map
                if uid not in self._display_ordered_citation_map:
                    self._display_ordered_citation_map[uid] = source

        # Also ensure cumulative sources are accessible for lookup
        for uid, source_info in self._cumulative_src_map.items():
            if uid not in self._display_ordered_citation_map:
                # Convert cumulative source format to citation format for frontend compatibility
                self._display_ordered_citation_map[uid] = {
                    "id": uid,
                    "display_id": "1",  # Fallback display ID
                    "title": source_info.get("title", ""),
                    "content": source_info.get("content", ""),
                    "parent_id": source_info.get("parent_id", ""),
                    "is_procedural": source_info.get("is_procedural", False)
                }

        # For debug: Print lists of all preserved and current IDs
        all_source_ids = list(sorted(self._display_ordered_citation_map.keys()))
        current_ids = list(sorted(self._display_ordered_citations))
        print("\n--- CITATION DEBUG ---")
        print(f"ALL PRESERVED SOURCE IDs ({len(all_source_ids)}): {all_source_ids}")
        print(f"CURRENT MESSAGE SOURCE IDs ({len(current_ids)}): {current_ids}")

        import logging
        logging.info(f"ALL PRESERVED SOURCE IDs ({len(all_source_ids)}): {all_source_ids}")
        logging.info(f"CURRENT MESSAGE SOURCE IDs ({len(current_ids)}): {current_ids}")

        # Persist citation map to Redis
        self._save_citation_map_to_redis()
    def _deduplicate_by_document(self, results: List[Dict]) -> List[Dict]:
        """
        Deduplicate results by (title, parent_id) while preserving order and selecting best chunk.
        This prevents the citation mismatch issue by ensuring LLM only sees unique documents.
        """
        logger.info(f"Deduplicating {len(results)} results by document")
        
        seen_docs = {}  # (title, parent_id) -> best_result
        
        for result in results:
            doc_key = (result.get("title", ""), result.get("parent_id", ""))
            
            if doc_key not in seen_docs:
                # First chunk from this document
                seen_docs[doc_key] = result
                logger.debug(f"First chunk from document: {result.get('title', 'Untitled')}")
            else:
                # Additional chunk from same document - keep the one with higher relevance
                existing = seen_docs[doc_key] 
                if result.get("relevance", 0) > existing.get("relevance", 0):
                    seen_docs[doc_key] = result
                    logger.debug(f"Replaced chunk for document: {result.get('title', 'Untitled')} (better relevance)")
        
        # Return in original order, preserving the priority sequence
        unique_results = []
        seen_keys = set()
        for result in results:
            doc_key = (result.get("title", ""), result.get("parent_id", ""))
            if doc_key not in seen_keys and seen_docs[doc_key] == result:
                unique_results.append(result)
                seen_keys.add(doc_key)
        
        logger.info(f"Deduplicated to {len(unique_results)} unique documents")
        return unique_results

    # Default system prompt
    DEFAULT_SYSTEM_PROMPT = """
    ### Task:

    Respond to the user query using the provided context, incorporating inline citations in the format [id] **only when the <source> tag includes an explicit id attribute** (e.g., <source id="1">).
    
    ### Guidelines:

    - If you don't know the answer, clearly state that.
    - If uncertain, ask the user for clarification.
    - Respond in the same language as the user's query.
    - If the context is unreadable or of poor quality, inform the user and provide the best possible answer.
    - **Only include inline citations using [id] (e.g., [1], [2]) when the <source> tag includes an id attribute.**
    - Do not cite if the <source> tag does not contain an id attribute.
    - Do not use XML tags in your response.
    - Ensure citations are concise and directly related to the information provided.
    - Maintain continuity with previous conversation by referencing earlier exchanges when appropriate.
    - **IMPORTANT: For follow-up questions, continue to use citations [id] when referencing information from the provided context, even if you've mentioned this information in previous responses.**
    - **Always cite your sources in every response, including follow-up questions.**
    
    ### Example of Citation:

    If the user asks about a specific topic and the information is found in a source with a provided id attribute, the response should include the citation like in the following example:

    * "According to the study, the proposed method increases efficiency by 20% [1]."
    
    ### Follow-up Questions:
    
    For follow-up questions, you must continue to cite sources. For example:
    
    User: "What are the key features of Product X?"
    Assistant: "Product X has three main features: cloud integration [1], advanced analytics [2], and mobile support [3]."
    
    User: "Tell me more about the mobile support."
    Assistant: "The mobile support feature of Product X includes cross-platform compatibility, offline mode, and push notifications [3]."
    
    ### Output:

    Provide a clear and direct response to the user's query, including inline citations in the format [id] only when the <source> tag with id attribute is present in the context. Remember to include citations in ALL responses, including follow-up questions.
    
    <context>

    {{CONTEXT}}
    </context>
    
    <user_query>

    {{QUERY}}
    </user_query>
    """

    # Enhanced procedural system prompt for Phase 3
    PROCEDURAL_SYSTEM_PROMPT = """
    ### Task:
    
    Respond to the user query about procedural content using the provided context, incorporating inline citations in the format [id] **only when the <source> tag includes an explicit id attribute** (e.g., <source id="1">).
    
    ### Guidelines for Procedural Content:
    
    - Structure your response with clear hierarchical organization:
      * Use markdown headings (## for main sections, ### for subsections)
      * Group related steps under appropriate headings
      * Maintain a logical flow from prerequisites to completion
    
    - For step-by-step instructions:
      * Preserve the original sequence and numbering from the source material
      * Present steps in a clear, logical order from start to finish
      * Number each step explicitly (1, 2, 3, etc.)
      * Include all necessary details for each step
      * Use bullet points for sub-steps or additional details within a step
    
    - Ensure completeness:
      * Include all necessary prerequisites before listing steps
      * Specify where to start the procedure (e.g., which menu, screen, or interface)
      * Include any required materials, permissions, or preconditions
      * Conclude with verification steps or expected outcomes
      * Mention any common issues or troubleshooting tips if available
    
    - Always include inline citations using [id] format when referencing information from sources
      * Citations should appear at the end of the relevant step or section
      * Every factual claim should have a citation
      * **IMPORTANT: For follow-up questions, continue to use citations [id] when referencing information from the provided context, even if you've mentioned this information in previous responses**
    
    ### Example Format for Procedures:
    
    ## How to [Accomplish Task]
    
    ### Prerequisites
    - [Required materials or permissions] [1]
    - [System requirements or conditions] [1]
    
    ### [First Major Section]
    1. **[Step Name]**: [Detailed instructions for step 1] [1]
       - [Additional details or tips]
       - [Alternative approaches if applicable]
    
    2. **[Step Name]**: [Detailed instructions for step 2] [2]
       - [Additional details or tips]
    
    ### [Second Major Section]
    3. **[Step Name]**: [Detailed instructions for step 3] [2]
       - [Additional details or tips]
    
    4. **[Step Name]**: [Detailed instructions for step 4] [3]
       - [Additional details or tips]
    
    ### Verification
    - [How to confirm successful completion] [3]
    - [Expected outcome or result] [3]
    
    ### General Guidelines:
    
    - If you don't know the answer, clearly state that.
    - If uncertain, ask the user for clarification.
    - Respond in the same language as the user's query.
    - If the context is unreadable or of poor quality, inform the user and provide the best possible answer.
    - **Only include inline citations using [id] (e.g., [1], [2]) when the <source> tag includes an id attribute.**
    - Do not cite if the <source> tag does not contain an id attribute.
    - Do not use XML tags in your response.
    - Maintain continuity with previous conversation by referencing earlier exchanges when appropriate.
    - **Always cite your sources in every response, including follow-up questions.**
    
    ### Output:
    
    Provide a clear, structured response that follows these guidelines while incorporating information from the context. Remember to include citations in ALL responses, including follow-up questions.
    
    <context>

    {{CONTEXT}}
    </context>
    
    <user_query>

    {{QUERY}}
    </user_query>
    """

    # ───────────────────────── setup ─────────────────────────

    def _init_cfg(self) -> None:
        self.openai_endpoint      = OPENAI_ENDPOINT
        self.openai_key           = OPENAI_KEY
        self.openai_api_version   = OPENAI_API_VERSION
        self.embedding_deployment = EMBEDDING_DEPLOYMENT
        self.deployment_name      = CHAT_DEPLOYMENT
        self.search_endpoint      = SEARCH_ENDPOINT
        self.search_index         = SEARCH_INDEX
        self.search_key           = SEARCH_KEY
        self.vector_field         = VECTOR_FIELD
        
    def _load_settings(self) -> None:
        """Load settings from provided settings dict"""
        settings = self.settings
        
        # Update model parameters
        if "model" in settings:
            self.deployment_name = settings["model"]
            # Update the OpenAI service deployment name
            self.openai_service.deployment_name = self.deployment_name
            
        if "temperature" in settings:
            self.temperature = settings["temperature"]
        if "top_p" in settings:
            self.top_p = settings["top_p"]
        if "max_completion_tokens" in settings:
            if settings["max_completion_tokens"] is not None:
                self.max_completion_tokens = settings["max_completion_tokens"]
        
        # Update search configuration
        if "search_index" in settings:
            self.search_index = settings["search_index"]
            
        # Update conversation history window size
        if "max_history_turns" in settings:
            self.max_history_turns = settings["max_history_turns"]
            logger.info(f"Setting max_history_turns to {self.max_history_turns}")

        # Update summarization settings
        if "summarization_settings" in settings:
            self.summarization_settings.update(settings.get("summarization_settings", {}))
            logger.info(f"Updated summarization settings: {self.summarization_settings}")

        
        # Update system prompt if provided
        if "system_prompt" in settings:
            system_prompt = settings.get("system_prompt", "")
            system_prompt_mode = settings.get("system_prompt_mode", "Append")
            
            if system_prompt_mode == "Override":
                # Replace the default system prompt
                self.conversation_manager.clear_history(preserve_system_message=False)
                self.conversation_manager.chat_history = [{"role": "system", "content": system_prompt}]
                logger.info(f"System prompt overridden with custom prompt")
            else:  # Append
                # Update the system message with combined prompt
                combined_prompt = f"{system_prompt}\n\n{self.DEFAULT_SYSTEM_PROMPT}"
                self.conversation_manager.clear_history(preserve_system_message=False)
                self.conversation_manager.chat_history = [{"role": "system", "content": combined_prompt}]
                logger.info(f"System prompt appended with custom prompt")

    # ───────────── embeddings ─────────────
    def generate_embedding(self, text: str) -> Optional[List[float]]:
        if not text:
            return None
        try:
            request = {
                # Arguments for self.openai_client.embeddings.create
                'model': self.embedding_deployment,
                'input': text.strip(),
            }
            resp = self.openai_client.embeddings.create(**request)
            log_openai_call(request, resp)
            return resp.data[0].embedding
            
        
        except Exception as exc:
            logger.error("Embedding error: %s", exc)
            return None

    @staticmethod
    def cosine_similarity(a: List[float], b: List[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        mag = (sum(x * x for x in a) ** 0.5) * (sum(y * y for y in b) ** 0.5)
        return 0.0 if mag == 0 else dot / mag

    # ───────────── Azure Search ───────────
    def search_knowledge_base(self, query: str) -> List[Dict]:
        try:
            logger.info(f"Searching knowledge base for query: {query}")
            client = SearchClient(
                endpoint=f"https://{self.search_endpoint}.search.windows.net",
                index_name=self.search_index,
                credential=AzureKeyCredential(self.search_key),
            )
            q_vec = self.generate_embedding(query)
            if not q_vec:
                logger.error("Failed to generate embedding for query")
                return []

            logger.info(f"Executing vector search with fields: {self.vector_field}")
            vec_q = VectorizedQuery(
                vector=q_vec,
                k_nearest_neighbors=10,
                fields=self.vector_field,
            )
            
            # Log the search parameters
            logger.info(f"Search parameters: index={self.search_index}, vector_field={self.vector_field}, top=10")
            
            # Add parent_id to select fields
            results = client.search(
                search_text=query,
                vector_queries=[vec_q],
                select=["chunk", "title", "parent_id"],  # Added parent_id here
                top=10,
            )
            
            # Convert results to list and log count
            result_list = list(results)
            logger.info(f"Search returned {len(result_list)} results")
            
            # Debug log the first result if available
            if result_list and len(result_list) > 0:
                first_result = result_list[0]
                logger.debug(f"First result - title: {first_result.get('title', 'No title')}")
                logger.debug(f"First result - has parent_id: {'Yes' if 'parent_id' in first_result else 'No'}")
                if 'parent_id' in first_result:
                    logger.debug(f"First result - parent_id: {first_result.get('parent_id')[:30]}..." if first_result.get('parent_id') else "None")
            
            # Convert results to standard format
            standard_results = [
                {
                    "chunk": r.get("chunk", ""),
                    "title": r.get("title", "Untitled"),
                    "parent_id": r.get("parent_id", ""),  # Include parent_id
                    "relevance": 1.0,
                }
                for r in result_list
            ]
            
            # Apply hierarchical retrieval to preserve document structure
            organized_results = retrieve_with_hierarchy(standard_results)
            
            return organized_results
        except Exception as exc:
            logger.error(f"Search error: {exc}", exc_info=True)
            logger.error(f"Traceback: {traceback.format_exc()}")
            return []

    # ───────── context & citations ────────

    def _trim_history(self, messages: List[Dict]) -> Tuple[List[Dict], bool]:
        """Trim conversation history to the last N turns while preserving the system message."""
        logger.info(
            f"TRIM_DEBUG: Called with {len(messages)} messages. Cap is {self.max_history_turns*2+1}"
        )
        dropped = False
        if len(messages) > self.max_history_turns * 2 + 1:  # +1 for system message
            dropped = True
            logger.info(
                f"History size ({len(messages)}) exceeds limit ({self.max_history_turns*2+1}), trimming..."
            )
            logger.info(f"Before trimming: {len(messages)} messages")

            # Preserve system message
            system_msg = messages[0]
            recent_messages = messages[-self.max_history_turns * 2 :]
            old_messages = messages[1 : len(messages) - len(recent_messages)]

            # If summarization is enabled, summarize the dropped history
            if self.summarization_settings.get("enabled", False) and old_messages:
                summary = self._summarize_messages(old_messages)
                summary_msg = {
                    "role": "system",
                    "content": f"[Summary of earlier conversation]\n{summary}",
                }
                messages = [system_msg, summary_msg] + recent_messages
            else:
                messages = [system_msg] + recent_messages

            logger.info(f"After trimming: {len(messages)} messages")
            logger.info(f"Trimmed conversation history to last {self.max_history_turns} turns")
            self._history_trimmed = True
        else:
            self._history_trimmed = False
            logger.info(
                f"No trimming needed. History size: {len(messages)}, limit: {self.max_history_turns*2+1}"
            )

        return messages, dropped

    def _summarize_messages(self, messages: List[Dict]) -> str:
        """Summarize only the last user question and assistant response, including source titles."""
        summary_temp = self.summarization_settings.get("summary_temperature", 0.3)
        max_tokens = self.summarization_settings.get("max_summary_tokens", 800)

        # Extract the last user question and assistant reply
        last_user = next((m['content'] for m in reversed(messages) if m['role'] == 'user'), "")
        last_assistant = next((m['content'] for m in reversed(messages) if m['role'] == 'assistant'), "")

        # Collect document titles from last search context
        titles = []
        if hasattr(self, "_last_src_map"):
            titles = [info.get("title", "Untitled") for info in self._last_src_map.values()]
        titles_str = "; ".join(titles)

        # Build the summarization prompt
        prompt_text = (
            f"Summarize the following exchange. Docs used: {titles_str}\n"
            f"User: {last_user}\n"
            f"Assistant: {last_assistant}\n"
            f"Do not include page numbers or citations, only mention titles if necessary."
        )

        msg_payload = [{"role": "user", "content": prompt_text}]

        # Call the OpenAI service for summarization
        if self.deployment_name == CHAT_DEPLOYMENT_O4_MINI:
            return self.openai_service.get_chat_response(
                messages=msg_payload,
                max_completion_tokens=max_tokens,
            )
        return self.openai_service.get_chat_response(
            messages=msg_payload,
            max_completion_tokens=max_tokens,
        )

    def _prepare_context(self, results: List[Dict]) -> Tuple[str, Dict]:
        logger.info(f"Preparing context from {len(results)} search results")
        
        # Prioritize procedural content in the results
        prioritized_results = prioritize_procedural_content(results)
        logger.info(f"Results prioritized with procedural content first")
        
        # CRITICAL FIX: Apply deduplication BEFORE LLM processing to prevent citation mismatches
        unique_results = self._deduplicate_by_document(prioritized_results)
        logger.info(f"After deduplication: {len(unique_results)} unique documents to show LLM")
        
        entries, src_map = [], {}
        valid_chunks = 0
        
        # Track if we have procedural content
        has_procedural_content = False
        
        # Process the unique results (now guaranteed to be unique documents)
        for res in unique_results[:5]:
            chunk = res["chunk"].strip()
            if not chunk:
                logger.warning(f"Empty chunk found, skipping")
                continue

            valid_chunks += 1
            
            # Generate unique ID for this source
            unique_id = generate_unique_source_id(chunk)
            logger.info(f"Generated unique ID {unique_id} for source")
            
            # Check if this is procedural content
            is_proc = is_procedural_content(chunk)
            if is_proc:
                has_procedural_content = True
                logger.info(f"Source {unique_id} contains procedural content")
                formatted_chunk = format_procedural_context(chunk)
            else:
                formatted_chunk = format_context_text(chunk)
            
            # Log parent_id if available
            parent_id = res.get("parent_id", "")
            if parent_id:
                logger.info(f"Source {unique_id} has parent_id: {parent_id[:30]}..." if len(parent_id) > 30 else parent_id)
            else:
                logger.warning(f"Source {unique_id} missing parent_id")

            # Add metadata to the source entry
            metadata = res.get("metadata", {})
            metadata_str = ""
            if metadata:
                if metadata.get("is_procedural", False):
                    metadata_str = " data-procedural=\"true\""
                if "first_step" in metadata and "last_step" in metadata:
                    metadata_str += f" data-steps=\"{metadata['first_step']}-{metadata['last_step']}\""
            
            # Include metadata in the source tag with unique ID
            entries.append(f'<source id="{unique_id}"{metadata_str}>{formatted_chunk}</source>')
            
            src_map[unique_id] = {
                "title": res["title"],
                "content": formatted_chunk,
                "parent_id": parent_id,  # Include parent_id in source map
                "is_procedural": is_proc,  # Track if this is procedural content
                "metadata": metadata,  # Include full metadata
                "unique_id": unique_id  # Store the unique ID  
            }

        context_str = "\n\n".join(entries)
        if valid_chunks == 0:
            logger.warning("No valid chunks found in _prepare_context, returning fallback context")
            context_str = "[No context available from knowledge base]"

        logger.info(f"Prepared context with {valid_chunks} valid chunks and {len(src_map)} sources")
        logger.info(f"Context contains procedural content: {has_procedural_content}")
        # Save the last source map for summarization
        self._last_src_map = src_map

        # DEBUG: Log the entire src_map for troubleshooting
        import json
        try:
            pretty_src_map = json.dumps(
                {k: {"title": v.get("title", ""), "parent_id": v.get("parent_id", ""), "is_procedural": v.get("is_procedural", False)} for k, v in src_map.items()},
                indent=2
            )
            logger.info(f"DEBUG: Full src_map:\n{pretty_src_map}")
        except Exception as e:
            logger.error(f"Error logging src_map: {e}")
        
        return context_str, src_map

    def detect_query_type(self, query: str, conversation_history: List[Dict] = None) -> str:
        """
        Detect the user's intent to route the query appropriately using enhanced pattern matching,
        context analysis, and LLM-based mediation when needed.
        
        Args:
            query: The user query
            conversation_history: Optional conversation history for context
            
        Returns:
            One of: "HISTORY_RECALL", "CONTEXTUAL_FOLLOW_UP", "CONTEXTUAL_WITH_SEARCH",
                   "NEW_TOPIC_PROCEDURAL", "NEW_TOPIC_INFORMATIONAL"
        """
        logger.info(f"========== QUERY TYPE DETECTION ==========")
        logger.info(f"Query: '{query}'")
        
        # Get pattern-based classification
        query_type, confidence = self.pattern_matcher.classify_query(query, conversation_history)
        logger.info(f"Initial pattern-based classification: {query_type} (confidence: {confidence:.2f})")
        
        # Use the mediator to refine the classification, especially for complex cases
        mediator_result = self.query_mediator.classify(
            query=query,
            history=conversation_history,
            current_classification={query_type: confidence}
        )
        
        logger.info(f"Mediator result: {mediator_result}")
        
        # If the mediator provided a definitive classification, use it
        if mediator_result.get('source') == 'mediator':
            final_classification = mediator_result['classification']
            final_confidence = mediator_result.get('confidence', 0.8) # Default to high confidence for mediator
            logger.info(f"Using mediator classification: {final_classification} (confidence: {final_confidence:.2f})")
        else:
            final_classification = query_type
            final_confidence = confidence
            logger.info(f"Using pattern-based classification: {final_classification} (confidence: {final_confidence:.2f})")
            
        # Log the final decision
        self.routing_logger.log_decision(
            query=query,
            detected_type=final_classification,
            confidence=final_confidence,
            search_performed=final_classification in ["NEW_TOPIC_PROCEDURAL", "NEW_TOPIC_INFORMATIONAL", "CONTEXTUAL_WITH_SEARCH"],
            conversation_context=conversation_history,
            pattern_matches=mediator_result.get('reasoning', self.pattern_matcher.get_confidence_explanation(query, final_classification, final_confidence)),
            mediator_used=mediator_result.get('source') == 'mediator'
        )
        
        logger.info(f"========== FINAL CLASSIFICATION: {final_classification} ==========")
        return final_classification

    def _chat_answer_with_history(self, query: str, context: str, src_map: Dict) -> str:
        """Generate a response using the conversation history"""
        logger.info("Generating response with conversation history")
        
        # Detect query type
        query_type = self.detect_query_type(query)
        
        # Select appropriate system prompt based on query type
        if query_type == "procedural":
            system_prompt = self.PROCEDURAL_SYSTEM_PROMPT
            logger.info("Using procedural system prompt")
        else:
            system_prompt = self.DEFAULT_SYSTEM_PROMPT
            logger.info("Using default system prompt")
        
        # Update the system message without clearing history
        if self.conversation_manager.chat_history:
            self.conversation_manager.chat_history[0]["content"] = system_prompt
        else:
            self.conversation_manager.chat_history = [{"role": "system", "content": system_prompt}]
        
        # Check if custom prompt is available in settings
        settings = self.settings
        custom_prompt = settings.get("custom_prompt", "")
        
        # Apply custom prompt to query if available
        if custom_prompt:
            query = f"{custom_prompt}\n\n{query}"
            logger.info(f"Applied custom prompt to query: {custom_prompt[:100]}...")
        
        # Create a context message
        context_message = f"<context>\n{context}\n</context>\n<user_query>\n{query}\n</user_query>"
        
        # Add the user message to conversation history
        self.conversation_manager.add_user_message(context_message)
        
        # Get the complete conversation history
        raw_messages = self.conversation_manager.get_history()

        # Trim history if needed
        messages, trimmed = self._trim_history(raw_messages)
        if trimmed:
            messages.append({"role": "system", "content": f"[History trimmed to last {self.max_history_turns} turns]"})
        
        # Log the conversation history
        logger.info(f"Conversation history has {len(messages)} messages")
        for i, msg in enumerate(messages):
            logger.info(f"Message {i} - Role: {msg['role']}")
            if i < 3 or i >= len(messages) - 2:  # Log first 3 and last 2 messages
                logger.info(f"Content: {msg['content'][:100]}...")
        
        # Get response from OpenAI service
        import json
        payload = {
            "model": self.deployment_name,
            "messages": messages,
            "store": True,

          
        }
        if self.deployment_name == CHAT_DEPLOYMENT_O4_MINI:
            payload["max_completion_tokens"] = self.max_completion_tokens
        else:
            payload["max_completion_tokens"] = self.max_completion_tokens
        logger.info("========== OPENAI RAW PAYLOAD ==========")
        logger.info(json.dumps(payload, indent=2))
        if self.deployment_name == CHAT_DEPLOYMENT_O4_MINI:
            response = self.openai_service.get_chat_response(
                messages=messages,
                max_completion_tokens=self.max_completion_tokens,
               
            )
        else:
            response = self.openai_service.get_chat_response(
                messages=messages,
                max_completion_tokens=self.max_completion_tokens,
             
               
            )
        
        # Add the assistant's response to conversation history
        self.conversation_manager.add_assistant_message(response)
        
        return response

    def _filter_cited(self, answer: str, src_map: Dict) -> List[Dict]:
        logger.info("Filtering cited sources from answer")
        cited_sources = []
        
        # First, check for explicit citations in the format [id]
        explicit_citations = set()
        
        # Pattern for numeric citations [1], [2], etc. Map to src_map entries by index
        numeric_citation_pattern = r'\[(\d+)\]'
        numeric_matches = [m.group(1) for m in re.finditer(numeric_citation_pattern, answer)]
        keys = list(src_map.keys())
        for num in numeric_matches:
            try:
                idx = int(num) - 1
                if 0 <= idx < len(keys):
                    uid = keys[idx]
                    explicit_citations.add(uid)
                    logger.info(f"Mapped numeric citation [{num}] to source {uid}")
                else:
                    logger.warning(f"Numeric citation [{num}] out of range for src_map keys")
            except ValueError:
                logger.warning(f"Invalid numeric citation marker [{num}]")
        
        # Pattern for unique ID citations [S_timestamp_hash]
        unique_citation_pattern = r'\[(S_\d+_[a-zA-Z0-9]+)\]'
        for match in re.finditer(unique_citation_pattern, answer):
            sid = match.group(1)
            if sid in src_map:
                explicit_citations.add(sid)
                logger.info(f"Source {sid} is explicitly cited in the answer (unique ID)")
                
        # Debug logging to help diagnose citation issues
        logger.info(f"Answer text: {answer}")
        logger.info(f"Source map keys: {list(src_map.keys())}")
        logger.info(f"Explicit citations found: {explicit_citations}")
        
        # Add explicitly cited sources
        for sid in explicit_citations:
            sinfo = src_map[sid]
            parent_id = sinfo.get("parent_id", "")
            if parent_id:
                logger.info(f"Source {sid} has parent_id: {parent_id[:30]}..." if len(parent_id) > 30 else parent_id)
            else:
                logger.warning(f"Cited source {sid} missing parent_id")
            
            cited_source = {
                "id": sid,
                "title": sinfo["title"],
                "content": sinfo["content"],
                "parent_id": parent_id,
                "is_procedural": sinfo.get("is_procedural", False)
            }
            cited_sources.append(cited_source)
        
        # If no explicit citations found, check for content similarity
        # This helps with follow-up questions where the model might not include citation markers
        if not cited_sources and len(src_map) > 0:
            logger.info("No explicit citations found, checking for content similarity")
            
            # For follow-up questions, include the most relevant sources
            # This is a simple approach - in a production system, you might want to use
            # more sophisticated text similarity measures
            for sid, sinfo in src_map.items():
                # Check if significant content from the source appears in the answer
                source_content = sinfo["content"].lower()
                answer_lower = answer.lower()
                
                # Extract key sentences or phrases from the source
                source_sentences = re.split(r'(?<=[.!?])\s+', source_content)
                significant_content_found = False
                
                # Check if any significant sentences from the source appear in the answer
                for sentence in source_sentences:
                    # Only check sentences that are substantial enough to be meaningful
                    if len(sentence) > 30 and sentence in answer_lower:
                        significant_content_found = True
                        logger.info(f"Source {sid} content found in answer without explicit citation")
                        break
                
                # If significant content found, add this source
                if significant_content_found:
                    parent_id = sinfo.get("parent_id", "")
                    cited_source = {
                        "id": sid,
                        "title": sinfo["title"],
                        "content": sinfo["content"],
                        "parent_id": parent_id,
                        "is_procedural": sinfo.get("is_procedural", False)
                    }
                    cited_sources.append(cited_source)
        
        logger.info(f"Found {len(cited_sources)} cited sources (explicit and implicit)")
        return cited_sources

    def _assemble_cited_sources(self, answer: str, src_map: Dict[str, Any]) -> Tuple[List[Dict], Dict[str, str]]:
        """
        Per-message citation logic - only sources from THIS message's search results.
        Each message gets completely independent citation numbering starting from [1].
        """
        logger.info("--- Assembling Cited Sources (Message-Only) ---")
        
        # CRITICAL CHANGE: Only use sources from the current message (src_map), 
        # NOT from the cumulative map. This prevents citation mixing between messages.
        
        # Filter to only sources actually cited in this message's answer
        cited_sources = self._filter_cited(answer, src_map)
        
        # CRITICAL FIX: If no cited sources but we have a src_map (from search results),
        # ALWAYS create fallback sources for the sidebar AND citation map accessibility
        # This fixes the first message timing issue where sources appear but aren't clickable
        if not cited_sources and src_map:
            logger.warning("No cited sources found in answer; providing fallback source list from current search results for sidebar.")
            cited_sources = []
            for uid, src in list(src_map.items())[:5]:
                cited_sources.append({
                    "id": uid,
                    "title": src.get("title", ""),
                    "content": src.get("content", ""),
                    "parent_id": src.get("parent_id", ""),
                    "is_procedural": src.get("is_procedural", False)
                })
        
        # Deduplicate cited sources by document (title, parent_id)
        seen_docs = {}  # Maps doc_key to best_source
        unique_cited = []
        
        for source in cited_sources:
            doc_key = (source.get("title", ""), source.get("parent_id", ""))
            
            if doc_key not in seen_docs:
                seen_docs[doc_key] = source
                unique_cited.append(source)
                logger.info(f"New cited document: {source.get('title', 'Untitled')}")
            else:
                # Keep the source with higher relevance if available
                existing = seen_docs[doc_key]
                if source.get("relevance", 0) > existing.get("relevance", 0):
                    # Replace in the list
                    idx = unique_cited.index(existing)
                    unique_cited[idx] = source
                    seen_docs[doc_key] = source
                    logger.info(f"Replaced cited document: {source.get('title', 'Untitled')} (better relevance)")
        
        # Create per-message citation numbering starting from 1
        # IMPORTANT: This ensures each message has independent [1], [2], [3] etc.
        message_sources = []
        renumber_map = {}
        
        for i, source in enumerate(unique_cited, 1):
            display_id = str(i)
            unique_id = source["id"]
            
            message_sources.append({
                "id": unique_id,
                "display_id": display_id,
                "title": source.get("title", ""),
                "content": source.get("content", ""),
                "parent_id": source.get("parent_id", ""),
                "is_procedural": source.get("is_procedural", False),
                **({"url": source["url"]} if "url" in source else {})
            })
            
            # Map unique ID to display ID for this message
            renumber_map[unique_id] = display_id
            
            logger.info(f"Message citation [{display_id}] -> {source.get('title', 'Untitled')}")

        logger.info(f"Final per-message renumber_map: {renumber_map}")
        logger.info(f"Final message_sources count: {len(message_sources)}")
        logger.info("--- End Assembling Cited Sources ---")

        return message_sources, renumber_map

    # ─────────── public API ───────────────
    def generate_rag_response(
        self, query: str, is_enhanced: bool = False
    ) -> Tuple[str, List[Dict], List[Dict], Dict[str, Any], str]:
        """
        Generate a response using the intelligent RAG router, with per-message citation flagging.
        
        Args:
            query: The user query
            is_enhanced: A flag to indicate if the query is already enhanced
            
        Returns:
            answer, all_cited_sources_with_flag, [], evaluation, context
        """
        try:
            logger.info(f"========== STARTING RAG RESPONSE WITH INTELLIGENT ROUTING ==========")
            logger.info(f"Original query: {query}")
            
            # Step 1: Classify the query's intent using the router
            history = self.conversation_manager.get_history()
            query_type = self.detect_query_type(query, history)
            logger.info(f"Query classified as: {query_type}")
            
            context = ""
            src_map = {}
            
            # Step 2: Execute action based on intent
            if query_type in ["NEW_TOPIC_PROCEDURAL", "NEW_TOPIC_INFORMATIONAL", "CONTEXTUAL_WITH_SEARCH"]:
                logger.info(f"Handling '{query_type}'. Performing knowledge base search.")
                kb_results = self.search_knowledge_base(query)
                if not kb_results:
                    # For contextual search, it's okay to have no new results, just use history
                    if query_type == "CONTEXTUAL_WITH_SEARCH":
                        logger.warning("No new documents found for contextual search, proceeding with history.")
                        context = "[No new context provided for this turn. Answer based on the conversation history.]"
                        src_map = self._cumulative_src_map
                    else:
                        return (
                            "No relevant information found in the knowledge base.",
                            [],
                            [],
                            {},
                            "",
                        )
                else:
                    context, src_map = self._prepare_context(kb_results)
                    # Update cumulative source map for future reference
                    self._cumulative_src_map.update(src_map)
                    logger.info(f"Updated cumulative source map, now contains {len(self._cumulative_src_map)} sources")

            elif query_type in ["CONTEXTUAL_FOLLOW_UP", "HISTORY_RECALL"]:
                logger.info(f"Handling '{query_type}'. Skipping search and using conversation history.")
                # No new context is needed. The model will use the chat history.
                # We use the cumulative map for citation filtering.
                src_map = self._cumulative_src_map
                context = "[No new context provided for this turn. Answer based on the conversation history.]"
                logger.info(f"Using existing cumulative source map with {len(src_map)} sources")
            
            # If no context was set (e.g., no search results for a new topic), provide a fallback
            if not context:
                context = "[No relevant information found in the knowledge base.]"
                logger.warning("No context available, using fallback message")
                return (
                    "No relevant information found in the knowledge base.",
                    [],
                    [],
                    {},
                    "",
                )

            # Step 3: Generate the actual answer using chat
            answer = self._chat_answer_with_history(query, context, src_map)
            logger.info(f"Generated answer of length {len(answer)}")

            # Step 4: CRITICAL FIX - Only use sources from THIS message's search results
            # This prevents citations from mixing between different messages
            cited_sources, renumber_map = self._assemble_cited_sources(answer, src_map)

            # --- CORRECT RENUMBERRING IN-TEXT CITATIONS TO DISPLAY IDs ---
            # Build a mapping from all citation references in the answer ([N], [unique_id]) to the corresponding display ID.

            def renumber_citations(answer, cited_sources, renumber_map):
                # Step 1: Build an index of which original in-text markers correspond to which unique_id
                # We want: for every [N] or [S_...], map it to the unique id and thus to display id

                # Build a reverse index for numeric mapping: for answer [1], [2], etc.
                unique_ids = [src["id"] for src in cited_sources]
                display_ids = [src["display_id"] for src in cited_sources]
                # Build a mapping of possible numeric citation in LLM (1-based) to unique id used
                numeric_to_uid = {}
                for idx, uid in enumerate(unique_ids):
                    numeric_to_uid[str(idx + 1)] = uid  # [1] => unique_ids[0], etc.

                # Build a mapping of all to display_id for substitution
                # [S_...] => [display_id], [n] => [display_id] if matched
                def citation_replacer(match):
                    marker = match.group(1)
                    # Unique id style ([S_xxx_xxx])
                    if marker in renumber_map:
                        return f'[{renumber_map[marker]}]'
                    # Numeric style ([n]). Only map if the number corresponds to a cited source found in mapping
                    elif marker in numeric_to_uid and numeric_to_uid[marker] in renumber_map:
                        return f'[{renumber_map[numeric_to_uid[marker]]}]'
                    # Otherwise, leave as is (do not replace unrelated/unrecognized numbers)
                    return match.group(0)
                # Replace all [n] or [S_...] with correct display_id
                answer = re.sub(r'\[([A-Za-z0-9_]+)\]', citation_replacer, answer)
                return answer

            answer = renumber_citations(answer, cited_sources, renumber_map)

            # [NEW] Always rebuild citation map so UI always has correct state every request
            self._rebuild_citation_map(cited_sources)

            # Validate: check that all citations in answer ([N]) are present in cited_sources
            cited_display_ids = {c["display_id"] for c in cited_sources}
            missing_cits = set(re.findall(r'\[(\d+)\]', answer)) - cited_display_ids
            if missing_cits:
                logger.warning(f"Some citation numbers in answer have no corresponding source object: {missing_cits}")

            # ------ NEW: Ensure all unique id markers in the model answer are sources ------
            unique_id_cits = set(re.findall(r'\[([a-z0-9]{8,})\]', answer))
            cited_unique_ids = {c["id"] for c in cited_sources}
            missing_unique = unique_id_cits - cited_unique_ids
            for missing_uid in missing_unique:
                # Defensive: Add a placeholder entry if not found, so UI popup works (shows Not Available)
                logger.warning(f"Citation in answer uses ID not present in cited_sources: {missing_uid}")
                cited_sources.append({
                    "id": missing_uid,
                    "display_id": "-",
                    "title": "[Source not available]",
                    "content": "",
                    "parent_id": "",
                    "is_procedural": False
                })
            # ------ END NEW ------

            # DEBUG: Log first few lines of each cited source content
            for src in cited_sources:
                content_preview = "\n".join(src["content"].splitlines()[:3])
                truncated_title = src['title'] if len(src['title']) <= 40 else src['title'][:37] + "..."
                logger.info(f"Source {src['id']} <{truncated_title}> contains procedural content")
                logger.info(f"Citation ID: {src['id']}, Title: {src['title']}\nContent preview:\n{content_preview}\n---")

            logger.info(f"Processed {len(cited_sources)} cited sources (no renumbering applied, original IDs kept)")
            if cited_sources:
                logger.info(f"Example - Unique ID: {cited_sources[0]['id']}, Display ID: {cited_sources[0]['display_id']}")

            # --- NEW: Provide ALL citations with active flag ---
            # Current cited sources are the "active" (latest message) ones
            current_ids = set(src["id"] for src in cited_sources)
            all_citation_objs = []
            # Make a union of all prior sources (from self._display_ordered_citation_map) + current ones
            all_source_ids = set(self._display_ordered_citation_map.keys())
            for uid in all_source_ids:
                src = self._display_ordered_citation_map[uid]
                item = dict(src)  # Copy to avoid mutating internals
                # Add the activity flag:
                item["is_current_message"] = uid in current_ids
                all_citation_objs.append(item)

            # Step 6: (Optional) run fact check
            evaluation = self.fact_checker.evaluate_response(
                query=query,
                answer=answer,
                context=context,
                deployment=self.deployment_name,
            )
            
            # Step 7: Persist query + response + sources in your DB
            try:
                # Get the SQL query used to retrieve the results (if available)
                sql_query = None
                # If you have access to the actual SQL query used, set it here
                
                # Log the query to the database
                DatabaseManager.log_rag_query(
                    query=query,
                    response=answer,
                    sources=all_citation_objs,
                    context=context,
                    sql_query=sql_query
                )
                logger.info("Logged RAG query to database")
            except Exception as log_exc:
                logger.error(f"Error logging RAG query to database: {log_exc}")
                # Continue even if logging fails
            
            # Return all citations w/ activity status for UI to decide link vs disabled-link
            return answer, all_citation_objs, [], evaluation, context
        
        except Exception as exc:
            logger.error(f"RAG generation error: {exc}", exc_info=True)
            return (
                "I encountered an error while generating the response.",
                [],
                [],
                {},
                "",
            )
            
    def stream_rag_response(self, query: str) -> Generator[Union[str, Dict], None, None]:
        """
        Stream the RAG response generation with conversation history.
        
        Args:
            query: The user query
            
        Yields:
            Either string chunks of the answer or a dictionary with metadata
        """
        try:
            logger.info(f"========== STARTING STREAM RAG RESPONSE WITH HISTORY ==========")
            logger.info(f"Original query: {query}")
            
            # Step 1: Classify the query's intent using the router
            history = self.conversation_manager.get_history()
            query_type = self.detect_query_type(query, history)
            logger.info(f"Query classified as: {query_type}")
            
            context = ""
            src_map = {}
            
            # Step 2: Execute action based on intent
            if query_type in ["NEW_TOPIC_PROCEDURAL", "NEW_TOPIC_INFORMATIONAL", "CONTEXTUAL_WITH_SEARCH"]:
                logger.info(f"Handling '{query_type}'. Performing knowledge base search.")
                kb_results = self.search_knowledge_base(query)
                if kb_results:
                    context, src_map = self._prepare_context(kb_results)
                    # Update cumulative source map for future reference
                    self._cumulative_src_map.update(src_map)
                    logger.info(f"Updated cumulative source map, now contains {len(self._cumulative_src_map)} sources")
                elif query_type == "CONTEXTUAL_WITH_SEARCH":
                    logger.warning("No new documents found for contextual search, proceeding with history.")
                    context = "[No new context provided for this turn. Answer based on the conversation history.]"
                    src_map = self._cumulative_src_map

            elif query_type in ["CONTEXTUAL_FOLLOW_UP", "HISTORY_RECALL"]:
                logger.info(f"Handling '{query_type}'. Skipping search and using conversation history.")
                # No new context is needed. The model will use the chat history.
                # We use the cumulative map for citation filtering.
                src_map = self._cumulative_src_map
                context = "[No new context provided for this turn. Answer based on the conversation history.]"
                logger.info(f"Using existing cumulative source map with {len(src_map)} sources")
            
            # If no context was set (e.g., no search results for a new topic), provide a fallback
            if not context:
                context = "[No relevant information found in the knowledge base.]"
                logger.warning("No context available, using fallback message")
                yield "No relevant information found in the knowledge base."
                yield {
                    "sources": [],
                    "evaluation": {}
                }
                return
            
            # Select appropriate system prompt based on query type
            if query_type.endswith("PROCEDURAL"):
                system_prompt = self.PROCEDURAL_SYSTEM_PROMPT
                logger.info("Using procedural system prompt")
            else:
                system_prompt = self.DEFAULT_SYSTEM_PROMPT
                logger.info("Using default system prompt")
            
            # Update the system message without clearing history
            if self.conversation_manager.chat_history:
                self.conversation_manager.chat_history[0]["content"] = system_prompt
            else:
                self.conversation_manager.chat_history = [{"role": "system", "content": system_prompt}]
            
            # Check if custom prompt is available in settings
            settings = self.settings
            custom_prompt = settings.get("custom_prompt", "")
            
            # Apply custom prompt to query if available
            if custom_prompt:
                query = f"{custom_prompt}\n\n{query}"
                logger.info(f"Applied custom prompt to query: {custom_prompt[:100]}...")
            
            # Create a context message
            context_message = f"<context>\n{context}\n</context>\n<user_query>\n{query}\n</user_query>"
            
            # Add the user message to conversation history
            self.conversation_manager.add_user_message(context_message)
            
            # Get the complete conversation history
            raw_messages = self.conversation_manager.get_history()

            # Trim history if needed
            messages, trimmed = self._trim_history(raw_messages)
            if trimmed:
                yield {"trimmed": True, "dropped": len(raw_messages) - len(messages)}
            
            # Log the conversation history
            logger.info(f"Conversation history has {len(messages)} messages")
            for i, msg in enumerate(messages):
                logger.info(f"Message {i} - Role: {msg['role']}")
                if i < 3 or i >= len(messages) - 2:  # Log first 3 and last 2 messages
                    logger.info(f"Content: {msg['content'][:100]}...")
            
            # Stream the response
            collected_chunks = []
            collected_answer = ""
            
            # Use the OpenAI client directly for streaming since our OpenAIService doesn't support streaming yet
            request = {
                # Arguments for self.openai_client.chat.completions.create
                'model': self.deployment_name,
                'store': True,
                'messages': messages,
            }
            if self.deployment_name == CHAT_DEPLOYMENT:
                request['temperature'] = self.temperature
                request['top_p'] = self.top_p
            request.update({
                'presence_penalty': self.presence_penalty,
                'frequency_penalty': self.frequency_penalty,
                'stream': True
            })
            if self.deployment_name == CHAT_DEPLOYMENT_O4_MINI:
                request['max_completion_tokens'] = self.max_completion_tokens
            else:
                request['max_completion_tokens'] = self.max_completion_tokens
            log_openai_call(request, {"type": "stream_started"})
            stream = self.openai_client.chat.completions.create(**request)
            
            # Process the streaming response
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    collected_chunks.append(content)
                    collected_answer += content
                    yield content
            
            logger.info("DEBUG - Collected answer: %s", collected_answer[:100])
            
            # Add the assistant's response to conversation history
            self.conversation_manager.add_assistant_message(collected_answer)
            
            # CRITICAL FIX - Use only THIS message's sources for citation assembly
            # This prevents citations from mixing between different messages
            cited_sources, renumber_map = self._assemble_cited_sources(collected_answer, src_map)

            # CRITICAL FIX: If no cited sources but we have a src_map (from search results),
            # ALWAYS create fallback sources for the sidebar AND citation map accessibility
            # This fixes the first message timing issue where sources appear but aren't clickable
            if not cited_sources and src_map:
                logger.warning("No cited sources found in answer; providing fallback source list from current search results for sidebar.")
                cited_sources = []
                display_num = 1
                for uid, src in list(src_map.items())[:5]:
                    cited_sources.append({
                        "id": uid,
                        "display_id": str(display_num),
                        "title": src.get("title", ""),
                        "content": src.get("content", ""),
                        "parent_id": src.get("parent_id", ""),
                        "is_procedural": src.get("is_procedural", False)
                    })
                    display_num += 1
            # Additional fallback: If still no cited sources but we have cumulative sources
            elif not cited_sources and self._cumulative_src_map:
                logger.warning("No cited sources found; providing fallback from cumulative sources.")
                cited_sources = []
                seen_keys = set()
                display_num = 1
                for uid, src in list(self._cumulative_src_map.items())[:5]:
                    doc_key = (src.get("title", ""), src.get("parent_id", ""))
                    if doc_key in seen_keys:
                        continue
                    seen_keys.add(doc_key)
                    cited_sources.append({
                        "id": uid,
                        "display_id": str(display_num),
                        "title": src.get("title", ""),
                        "content": src.get("content", ""),
                        "parent_id": src.get("parent_id", ""),
                        "is_procedural": src.get("is_procedural", False)
                    })
                    display_num += 1

            # CRITICAL: Always rebuild citation map with cited sources to ensure accessibility
            self._rebuild_citation_map(cited_sources)
            
            # DO NOT remap unique citation IDs to display numbering; keep as original IDs.
            logger.info(f"Processed {len(cited_sources)} cited sources (no renumbering applied, original IDs kept)")
            if cited_sources:
                logger.info(f"Example - Unique ID: {cited_sources[0]['id']}, Display ID: {cited_sources[0]['display_id']}")
            
            # Get evaluation
            evaluation = self.fact_checker.evaluate_response(
                query=query,
                answer=collected_answer,
                context=context,
                deployment=self.deployment_name,
            )
            
            # Log the query, response, and sources to the database
            try:
                # Get the SQL query used to retrieve the results (if available)
                sql_query = None
                # If you have access to the actual SQL query used, set it here
                
                # Log the query to the database
                DatabaseManager.log_rag_query(
                    query=query,
                    response=collected_answer,
                    sources=cited_sources,
                    context=context,
                    sql_query=sql_query
                )
            except Exception as log_exc:
                logger.error(f"Error logging RAG query to database: {log_exc}")
                # Continue even if logging fails
            
            # Yield the metadata
            yield {
                "sources": cited_sources,
                "evaluation": evaluation
            }
            
        except Exception as exc:
            logger.error(f"RAG streaming error: {exc}", exc_info=True)
            yield "I encountered an error while generating the response."
            yield {
                "sources": [],
                "evaluation": {},
                "error": str(exc)
            }
    
    def clear_conversation_history(self, preserve_system_message: bool = True) -> None:
        """
        Clear the conversation history.
        
        Args:
            preserve_system_message: Whether to preserve the initial system message
        """
        self.conversation_manager.clear_history(preserve_system_message)
        logger.info(f"Conversation history cleared (preserve_system_message={preserve_system_message})")


# Test functions for Phase 1
def test_semantic_chunking():
    """Test the semantic chunking function"""
    test_logger.info("Running test_semantic_chunking")
    
    sample_doc = """# Adding a Calendar
    
    ## Basic Information
    1. Enter a name for the calendar
    2. Provide a description
    
    ## Time Settings
    1. Set minimum reservation time
    2. Set maximum reservation time"""
    
    chunks = chunk_document(sample_doc)
    
    # Verify chunks preserve headers and numbered steps
    assert len(chunks) > 0, "Chunking should produce at least one chunk"
    assert "# Adding a Calendar" in chunks[0], "First chunk should contain the main header"
    
    # Check if numbered steps are preserved in any chunk
    steps_preserved = any("1. Enter a name" in chunk for chunk in chunks)
    assert steps_preserved, "Chunks should preserve numbered steps"
    
    # Check if section headers are preserved in any chunk
    headers_preserved = any("## Time Settings" in chunk for chunk in chunks)
    assert headers_preserved, "Chunks should preserve section headers"
    
    test_logger.info("test_semantic_chunking passed")
    return True


def test_procedural_content_detection():
    """Test the procedural content detection function"""
    test_logger.info("Running test_procedural_content_detection")
    
    procedural_text = "1. Enter a name for the calendar\n2. Provide a description"
    informational_text = "Calendars are used to schedule events and manage time."
    
    assert is_procedural_content(procedural_text) == True, "Should detect numbered steps as procedural"
    assert is_procedural_content(informational_text) == False, "Should not detect informational text as procedural"
    
    # Test with instructional keywords
    keyword_text = "Follow these steps to create a calendar."
    assert is_procedural_content(keyword_text) == True, "Should detect instructional keywords as procedural"
    
    test_logger.info("test_procedural_content_detection passed")
    return True


def test_metadata_extraction():
    """Test the metadata extraction function"""
    test_logger.info("Running test_metadata_extraction")
    
    chunk = "## Adding a Calendar\n\n1. Navigate to Settings\n2. Click on Add Calendar"
    metadata = extract_metadata(chunk)
    
    assert metadata["is_procedural"] == True, "Should detect procedural content"
    assert "steps" in metadata, "Should extract step numbers"
    assert metadata["steps"] == [1, 2], "Should extract correct step numbers"
    assert metadata["first_step"] == 1, "Should identify first step"
    assert metadata["last_step"] == 2, "Should identify last step"
    
    test_logger.info("test_metadata_extraction passed")
    return True


def run_phase1_tests():
    """Run all Phase 1 tests"""
    checkpoint_logger.info("Running Phase 1 tests")
    
    tests = [
        test_semantic_chunking,
        test_procedural_content_detection,
        test_metadata_extraction
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            test_logger.error(f"Test {test.__name__} failed: {e}")
            results.append(False)
    
    success = all(results)
    if success:
        checkpoint_logger.info("All Phase 1 tests passed")
    else:
        checkpoint_logger.error("Some Phase 1 tests failed")
    
    return success


# Test functions for Phase 2
def test_procedural_context_formatting():
    """Test the procedural context formatting function"""
    test_logger.info("Running test_procedural_context_formatting")
    
    procedural_text = "1. Enter a name for the calendar\n2. Provide a description"
    formatted = format_procedural_context(procedural_text)
    
    # Verify formatting preserves numbered steps
    assert "1. Enter" in formatted, "Should preserve step 1"
    assert "2. Provide" in formatted, "Should preserve step 2"
    
    # Test with section headers
    header_text = "BASIC INFORMATION: This section contains details about the calendar."
    formatted_header = format_procedural_context(header_text)
    
    # Verify headers are emphasized
    assert "**BASIC INFORMATION:**" in formatted_header, "Should emphasize headers"
    
    test_logger.info("test_procedural_context_formatting passed")
    return True


def test_prioritize_procedural_content():
    """Test the prioritization of procedural content"""
    test_logger.info("Running test_prioritize_procedural_content")
    
    # Create sample results with mixed content
    results = [
        {
            "chunk": "Calendars are used to schedule events and manage time.",
            "title": "Calendar Overview",
            "parent_id": "doc1",
            "relevance": 0.9
        },
        {
            "chunk": "1. Enter a name for the calendar\n2. Provide a description",
            "title": "Adding a Calendar",
            "parent_id": "doc2",
            "relevance": 0.8
        },
        {
            "chunk": "The system supports multiple calendar views.",
            "title": "Calendar Views",
            "parent_id": "doc3",
            "relevance": 0.7
        }
    ]
    
    # Prioritize the results
    prioritized = prioritize_procedural_content(results)
    
    # Verify procedural content is first
    assert "1. Enter" in prioritized[0]["chunk"], "Procedural content should be first"
    assert len(prioritized) == 3, "Should preserve all results"
    
    # Test with multiple procedural chunks
    results.append({
        "chunk": "1. Go to Settings\n2. Select Calendar tab",
        "title": "Accessing Calendar Settings",
        "parent_id": "doc4",
        "relevance": 0.6,
        "metadata": {
            "is_procedural": True,
            "first_step": 1,
            "last_step": 2
        }
    })
    
    # Prioritize again
    prioritized = prioritize_procedural_content(results)
    
    # Verify both procedural chunks are first
    assert len([r for r in prioritized[:2] if is_procedural_content(r["chunk"])]) == 2, "Should have 2 procedural chunks first"
    
    test_logger.info("test_prioritize_procedural_content passed")
    return True


def run_phase2_tests():
    """Run all Phase 2 tests"""
    checkpoint_logger.info("Running Phase 2 tests")
    
    tests = [
        test_procedural_context_formatting,
        test_prioritize_procedural_content
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            test_logger.error(f"Test {test.__name__} failed: {e}")
            results.append(False)
    
    success = all(results)
    if success:
        checkpoint_logger.info("All Phase 2 tests passed")
    else:
        checkpoint_logger.error("Some Phase 2 tests failed")
    
    return success


# ─────────── Phase 3: System Prompt Improvements ───────────

def test_query_type_detection():
    """Test the enhanced query type detection function"""
    test_logger.info("Running test_query_type_detection")
    
    # Create a test instance
    rag_assistant = FlaskRAGAssistantV2()
    
    # Test procedural queries
    procedural_queries = [
        "How to add a new calendar?",
        "What are the steps to configure calendar permissions?",
        "Guide me through setting up a calendar",
        "I need to create a new calendar, what's the process?",
        "Can you show me how to add a calendar?",
        "Steps for creating a calendar",
        "What's the procedure to set up recurring events?",
        "Explain the process of adding a calendar",
        "Walk me through calendar creation"
    ]
    
    for query in procedural_queries:
        query_type = rag_assistant.detect_query_type(query)
        assert query_type == "procedural", f"Query '{query}' should be detected as procedural"
    
    # Test informational queries
    informational_queries = [
        "What is a calendar?",
        "Tell me about calendar features",
        "When was the calendar system released?",
        "Who can access the calendar?",
        "What are the benefits of using calendars?",
        "Are there any limitations to calendar sharing?",
        "What types of calendars are available?",
        "Is the calendar system compatible with mobile devices?"
    ]
    
    for query in informational_queries:
        query_type = rag_assistant.detect_query_type(query)
        assert query_type == "informational", f"Query '{query}' should be detected as informational"
    
    # Test follow-up queries with conversation context
    conversation_history = [
        {"role": "user", "content": "How do I create a calendar?"},
        {"role": "assistant", "content": "To create a calendar, follow these steps: 1. Go to settings..."}
    ]
    
    follow_up_queries = [
        "What's next?",
        "Then what?",
        "Continue",
        "What about permissions?",
        "How do I share it?"
    ]
    
    for query in follow_up_queries:
        query_type = rag_assistant.detect_query_type(query, conversation_history)
        assert query_type == "procedural", f"Follow-up query '{query}' should be detected as procedural with conversation context"
    
    test_logger.info("test_query_type_detection passed")
    return True


def test_prompt_selection():
    """Test the prompt selection logic based on query type"""
    test_logger.info("Running test_prompt_selection")
    
    # Create a test instance
    rag_assistant = FlaskRAGAssistantV2()
    
    # Mock context and src_map for testing
    context = "<source id=\"1\">Test context</source>"
    src_map = {"1": {"title": "Test", "content": "Test content"}}
    
    # Mock the OpenAI service to avoid actual API calls
    original_get_chat_response = rag_assistant.openai_service.get_chat_response
    
    def mock_get_chat_response(messages, temperature=0.3, max_completion_tokens=1000, top_p=1.0):
        # Just return a dummy response
        return "This is a mock response."
    
    # Replace the method
    rag_assistant.openai_service.get_chat_response = mock_get_chat_response
    
    # Create a simpler test by directly checking the system prompt selection
    try:
        # Test with procedural query
        procedural_query = "How to add a calendar?"
        
        # Get the query type
        query_type = rag_assistant.detect_query_type(procedural_query)
        
        # Check if it's detected as procedural
        assert query_type == "procedural", "Query should be detected as procedural"
        
        # Test with informational query
        informational_query = "What is a calendar?"
        
        # Get the query type
        query_type = rag_assistant.detect_query_type(informational_query)
        
        # Check if it's detected as informational
        assert query_type == "informational", "Query should be detected as informational"
        
        # Test the prompt selection directly
        if rag_assistant.detect_query_type(procedural_query) == "procedural":
            system_prompt = rag_assistant.PROCEDURAL_SYSTEM_PROMPT
        else:
            system_prompt = rag_assistant.DEFAULT_SYSTEM_PROMPT
            
        # Check if procedural prompt was selected
        assert "Guidelines for Procedural Content" in system_prompt, "Procedural prompt should be selected for procedural query"
        
        # Test the prompt selection for informational query
        if rag_assistant.detect_query_type(informational_query) == "procedural":
            system_prompt = rag_assistant.PROCEDURAL_SYSTEM_PROMPT
        else:
            system_prompt = rag_assistant.DEFAULT_SYSTEM_PROMPT
            
        # Check if default prompt was selected
        assert "Guidelines for Procedural Content" not in system_prompt, "Default prompt should be selected for informational query"
        
    finally:
        # Restore original method
        rag_assistant.openai_service.get_chat_response = original_get_chat_response
    
    test_logger.info("test_prompt_selection passed")
    return True


def test_history_summarization():
    """Test that old history is summarized when trimming."""
    test_logger.info("Running test_history_summarization")

    rag_assistant = FlaskRAGAssistantV2()
    rag_assistant.summarization_settings["enabled"] = True

    # Mock summarization response
    def mock_get_chat_response(messages, temperature=0.3, max_completion_tokens=None, max_tokens=1000, top_p=1.0, presence_penalty=0.0, frequency_penalty=0.0):
        return "Summary"

    rag_assistant.openai_service.get_chat_response = mock_get_chat_response

    # Create history exceeding limit
    for i in range(12):
        rag_assistant.conversation_manager.add_user_message(f"U{i}")
        rag_assistant.conversation_manager.add_assistant_message(f"A{i}")

    messages = rag_assistant.conversation_manager.get_history()
    trimmed, dropped = rag_assistant._trim_history(messages)

    assert dropped is True, "History should be trimmed"
    assert any("Summary" in m["content"] for m in trimmed if m["role"] == "system"), "Summary message should be inserted"

    test_logger.info("test_history_summarization passed")
    return True


def run_phase3_tests():
    """Run all Phase 3 tests"""
    checkpoint_logger.info("Running Phase 3 tests")
    
    tests = [
        test_query_type_detection,
        test_prompt_selection,
        test_history_summarization
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            test_logger.error(f"Test {test.__name__} failed: {e}")
            results.append(False)
    
    success = all(results)
    if success:
        checkpoint_logger.info("All Phase 3 tests passed")
    else:
        checkpoint_logger.error("Some Phase 3 tests failed")
    
    return success


# Run tests if this file is executed directly
if __name__ == "__main__":
    print("=== Phase 1: Improved Chunking Strategy ===")
    phase1_success = run_phase1_tests()
    
    print("\n=== Phase 2: Context Preparation Enhancements ===")
    phase2_success = run_phase2_tests()
    
    print("\n=== Phase 3: System Prompt Improvements ===")
    phase3_success = run_phase3_tests()
    
    if phase1_success and phase2_success and phase3_success:
        print("\nAll tests passed!")
    else:
        print("\nSome tests failed. Check the logs for details.")
