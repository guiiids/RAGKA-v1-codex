"""
Improved version of the RAG assistant with better handling of procedural content
"""
import logging
from typing import List, Dict, Tuple, Optional, Any, Generator, Union
import traceback
from openai import AzureOpenAI
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from azure.core.credentials import AzureKeyCredential
import re
import sys
import os
import json
from openai_logger import log_openai_call
from db_manager import DatabaseManager
from conversation_manager import ConversationManager
from openai_service import OpenAIService
from rag_improvement_logging import get_phase_logger, get_checkpoint_logger, get_test_logger, get_compare_logger

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


class FlaskRAGAssistant:
    """Retrieval-Augmented Generation assistant with improved handling of procedural content."""

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
    def __init__(self, settings=None) -> None:
        self._init_cfg()
        
        # Initialize the OpenAI service
        self.openai_service = self._get_openai_service()
        
        # Initialize the conversation manager with the system prompt
        self.conversation_manager = ConversationManager(self.DEFAULT_SYSTEM_PROMPT)
        
        # For backward compatibility
        self.openai_client = self._get_openai_client()
        
        self.fact_checker = FactCheckerStub()
        
        # Model parameters with defaults
        self.temperature = 1.0
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
            "enabled": True,                # Whether to use summarization (vs. simple truncation)
            "max_summary_tokens": 800,      # Maximum length of summaries
            "summary_temperature": 0.3,     # Temperature for summary generation
        }
        
        # Load settings if provided
        self.settings = settings or {}
        self._load_settings()
        
        logger.info("FlaskRAGAssistant initialized with conversation history")

    def _init_cfg(self) -> None:
        self.azure_openai_endpoint = OPENAI_ENDPOINT
        self.azure_openai_key = OPENAI_KEY
        self.azure_openai_api_version = OPENAI_API_VERSION
        self.azure_openai_api_version_o4_mini = OPENAI_API_VERSION_O4_MINI
        self.embedding_deployment = EMBEDDING_DEPLOYMENT
        self.deployment_name = CHAT_DEPLOYMENT_O4_MINI # Default to o4-mini
        self.search_endpoint = SEARCH_ENDPOINT
        self.search_index = SEARCH_INDEX
        self.search_key = SEARCH_KEY
        self.vector_field = VECTOR_FIELD
        
    def _get_openai_client(self) -> AzureOpenAI:
        """Get the OpenAI client with the correct API version."""
        api_version = self.azure_openai_api_version
        if self.deployment_name == CHAT_DEPLOYMENT_O4_MINI:
            api_version = self.azure_openai_api_version_o4_mini
        
        logger.info(f"Creating AzureOpenAI client with API version: {api_version} from file: {__file__}")
            
        return AzureOpenAI(
            azure_endpoint=self.azure_openai_endpoint,
            api_key=self.azure_openai_key,
            api_version=api_version,
        )

    def _get_openai_service(self) -> OpenAIService:
        """Get the OpenAI service with the correct API version."""
        api_version = self.azure_openai_api_version
        if self.deployment_name == CHAT_DEPLOYMENT_O4_MINI:
            api_version = self.azure_openai_api_version_o4_mini
            
        logger.info(f"Creating OpenAIService with API version: {api_version} from file: {__file__}")

        return OpenAIService(
            azure_endpoint=self.azure_openai_endpoint,
            api_key=self.azure_openai_key,
            api_version=api_version,
            deployment_name=self.deployment_name
        )
        
    def _load_settings(self) -> None:
        """Load settings from provided settings dict"""
        settings = self.settings
        
        # Update model parameters
        if "model" in settings:
            self.deployment_name = settings["model"]
            # Update the OpenAI service
            self.openai_service = self._get_openai_service()
            # Update the OpenAI client
            self.openai_client = self._get_openai_client()
            
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
    def _prepare_context(self, results: List[Dict]) -> Tuple[str, Dict]:
        logger.info(f"Preparing context from {len(results)} search results")
        
        # Prioritize procedural content in the results
        prioritized_results = prioritize_procedural_content(results)
        logger.info(f"Results prioritized with procedural content first")
        
        entries, src_map = [], {}
        sid = 1
        valid_chunks = 0
        
        # Track if we have procedural content
        has_procedural_content = False
        
        # Process the top results (prioritized with procedural content first)
        for res in prioritized_results[:5]:
            chunk = res["chunk"].strip()
            if not chunk:
                logger.warning(f"Empty chunk found in result {sid}, skipping")
                continue

            valid_chunks += 1
            
            # Check if this is procedural content
            is_proc = is_procedural_content(chunk)
            if is_proc:
                has_procedural_content = True
                logger.info(f"Source {sid} contains procedural content")
                formatted_chunk = format_procedural_context(chunk)
            else:
                formatted_chunk = format_context_text(chunk)
            
            # Log parent_id if available
            parent_id = res.get("parent_id", "")
            if parent_id:
                logger.info(f"Source {sid} has parent_id: {parent_id[:30]}..." if len(parent_id) > 30 else parent_id)
            else:
                logger.warning(f"Source {sid} missing parent_id")

            # Add metadata to the source entry
            metadata = res.get("metadata", {})
            metadata_str = ""
            if metadata:
                if metadata.get("is_procedural", False):
                    metadata_str = " data-procedural=\"true\""
                if "first_step" in metadata and "last_step" in metadata:
                    metadata_str += f" data-steps=\"{metadata['first_step']}-{metadata['last_step']}\""
            
            # Include metadata in the source tag
            entries.append(f'<source id="{sid}"{metadata_str}>{formatted_chunk}</source>')
            
            src_map[str(sid)] = {
                "title": res["title"],
                "content": formatted_chunk,
                "parent_id": parent_id,  # Include parent_id in source map
                "is_procedural": is_proc,  # Track if this is procedural content
                "metadata": metadata  # Include full metadata
            }
            sid += 1

        context_str = "\n\n".join(entries)
        if valid_chunks == 0:
            logger.warning("No valid chunks found in _prepare_context, returning fallback context")
            context_str = "[No context available from knowledge base]"

        logger.info(f"Prepared context with {valid_chunks} valid chunks and {len(src_map)} sources")
        logger.info(f"Context contains procedural content: {has_procedural_content}")
        
        return context_str, src_map

    def detect_query_type(self, query: str, conversation_history: List[Dict] = None) -> str:
        """
        Detect if the query is asking for procedural information.
        
        Args:
            query: The user query
            conversation_history: Optional conversation history for context
            
        Returns:
            "procedural" or "informational"
        """
        # Enhanced procedural patterns
        procedural_patterns = [
            # How-to patterns
            r'how (to|do|can|would|should) (i|we|you|one)?\s',
            r'what (is|are) the (steps|procedure|process|way|method) (to|for|of)',
            r'(steps|procedure|process|method|approach) (to|for|of)',
            r'(guide|instructions|tutorial|walkthrough) (for|on|to)',
            r'(explain|describe|outline) (how|the steps|the process) (to|for)',
            
            # Action-oriented patterns
            r'(create|setup|configure|install|implement|build|deploy|run|execute)',
            r'(add|remove|delete|modify|update|change|edit|customize)',
            
            # Question patterns
            r'(what|which) (steps|actions) (should|do) (i|we|you) (take|follow)',
            r'(can|could) you (show|tell|walk) me (how|the steps) (to|for)',
            
            # Specific procedural keywords
            r'step[- ]by[- ]step',
            r'(workflow|walkthrough|tutorial)',
            r'(in order to|in what order)',
            
            # Follow-up patterns for procedural content
            r'(next step|after that|what next|then what|continue|proceed)',
            r'(first|second|third|fourth|fifth|last) step',
            r'(before|after) (i|we|you) (do|complete|finish)'
        ]
        
        # Check the current query
        query_lower = query.lower()
        
        # Special case for "guide me through" and similar phrases
        if re.search(r'(guide|walk|take) me through', query_lower) or re.search(r'(show|tell) me how', query_lower):
            logger.info(f"Query '{query}' detected as procedural based on guide/walk pattern")
            return "procedural"
            
        # Check other procedural patterns
        for pattern in procedural_patterns:
            if re.search(pattern, query_lower):
                logger.info(f"Query '{query}' detected as procedural based on pattern matching")
                return "procedural"
        
        # Check if this is a follow-up to a procedural query
        if conversation_history:
            # Look at the last few exchanges
            recent_history = conversation_history[-4:] if len(conversation_history) >= 4 else conversation_history
            
            # Check if there was a recent procedural query
            for message in recent_history:
                if message.get("role") == "user":
                    prev_query = message.get("content", "").lower()
                    # Check if previous query was procedural
                    for pattern in procedural_patterns:
                        if re.search(pattern, prev_query):
                            # This is likely a follow-up to a procedural query
                            logger.info(f"Query '{query}' detected as procedural based on conversation context")
                            return "procedural"
                            
                # Check if the assistant's previous response mentioned steps or procedures
                elif message.get("role") == "assistant":
                    prev_response = message.get("content", "").lower()
                    if re.search(r'(step \d+|first step|next step|following steps|procedure|process)', prev_response):
                        # The previous response was about steps or procedures
                        logger.info(f"Query '{query}' detected as procedural based on previous assistant response")
                        return "procedural"
        
        # Check for short follow-up queries that might be continuing a procedural conversation
        if len(query_lower.split()) <= 5:
            # Short queries like "What next?" or "Then what?" in a procedural context
            if re.search(r'(what|how|then|next|after|continue|more|details)', query_lower):
                if conversation_history and len(conversation_history) >= 2:
                    # Check the previous assistant message
                    for message in reversed(conversation_history):
                        if message.get("role") == "assistant":
                            prev_response = message.get("content", "").lower()
                            if re.search(r'(step \d+|first step|next step|following steps|procedure|process)', prev_response):
                                logger.info(f"Short query '{query}' detected as procedural follow-up")
                                return "procedural"
                            break
        
        logger.info(f"Query '{query}' detected as informational")
        return "informational"

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
        
        # Update the system message with the appropriate prompt
        self.conversation_manager.clear_history(preserve_system_message=False)
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
        messages = self.conversation_manager.get_history()
        
        # Log the conversation history
        logger.info(f"Conversation history has {len(messages)} messages")
        for i, msg in enumerate(messages):
            logger.info(f"Message {i} - Role: {msg['role']}")
            if i < 3 or i >= len(messages) - 2:  # Log first 3 and last 2 messages
                logger.info(f"Content: {msg['content'][:100]}...")
        
        # Get response from OpenAI service
        import json
        payload = {
            "messages": messages,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "frequency_penalty": self.frequency_penalty
        }

        if self.deployment_name == CHAT_DEPLOYMENT_O4_MINI:
            payload["max_completion_tokens"] = self.max_completion_tokens
        else:
            payload["max_completion_tokens"] = self.max_completion_tokens

        logger.info("========== OPENAI RAW PAYLOAD ==========")
        logger.info(json.dumps(payload, indent=2))
        response = self.openai_service.get_chat_response(
            messages=payload["messages"],
            temperature=payload["temperature"],
            top_p=payload["top_p"],
            max_completion_tokens=payload.get("max_completion_tokens")
        )
        
        # Add the assistant's response to conversation history
        self.conversation_manager.add_assistant_message(response)
        
        return response

    def _filter_cited(self, answer: str, src_map: Dict) -> List[Dict]:
        logger.info("Filtering cited sources from answer")
        cited_sources = []
        
        # First, check for explicit citations in the format [id]
        explicit_citations = set()
        citation_pattern = r'\[(\d+)\]'
        for match in re.finditer(citation_pattern, answer):
            sid = match.group(1)
            if sid in src_map:
                explicit_citations.add(sid)
                logger.info(f"Source {sid} is explicitly cited in the answer")
        
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

    # ─────────── public API ───────────────
    def generate_rag_response(
        self, query: str, is_enhanced: bool = False
    ) -> Tuple[str, List[Dict], List[Dict], Dict[str, Any], str]:
        """
        Generate a response using RAG with conversation history.
        
        Args:
            query: The user query
            is_enhanced: A flag to indicate if the query is already enhanced
            
        Returns:
            answer, cited_sources, [], evaluation, context
        """
        try:
            if not is_enhanced:
                # Use the original query for now (query enhancement will be added in a later phase)
                enhanced_query = query
            else:
                enhanced_query = query
                
            kb_results = self.search_knowledge_base(enhanced_query)
            if not kb_results:
                return (
                    "No relevant information found in the knowledge base.",
                    [],
                    [],
                    {},
                    "",
                )

            context, src_map = self._prepare_context(kb_results)
            
            # Use the conversation history to generate the answer
            answer = self._chat_answer_with_history(query, context, src_map)

            # Collect only the sources actually cited
            cited_raw = self._filter_cited(answer, src_map)

            # Renumber in cited order: 1, 2, 3…
            renumber_map = {}
            cited_sources = []
            for new_id, src in enumerate(cited_raw, 1):
                old_id = src["id"]
                renumber_map[old_id] = str(new_id)
                entry = {
                    "id": str(new_id), 
                    "title": src["title"], 
                    "content": src["content"],
                    "parent_id": src.get("parent_id", ""),  # Include parent_id in cited sources
                    "is_procedural": src.get("is_procedural", False)
                }
                if "url" in src:
                    entry["url"] = src["url"]
                cited_sources.append(entry)
            for old, new in renumber_map.items():
                answer = re.sub(rf"\[{old}\]", f"[{new}]", answer)

            evaluation = self.fact_checker.evaluate_response(
                query=query,
                answer=answer,
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
                    response=answer,
                    sources=cited_sources,
                    context=context,
                    sql_query=sql_query
                )
            except Exception as log_exc:
                logger.error(f"Error logging RAG query to database: {log_exc}")
                # Continue even if logging fails
            
            return answer, cited_sources, [], evaluation, context
        
        except Exception as exc:
            logger.error("RAG generation error: %s", exc)
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
            
            kb_results = self.search_knowledge_base(query)
            if not kb_results:
                logger.info("No relevant information found in knowledge base")
                yield "No relevant information found in the knowledge base."
                yield {
                    "sources": [],
                    "evaluation": {}
                }
                return

            context, src_map = self._prepare_context(kb_results)
            logger.info(f"Retrieved {len(kb_results)} results from knowledge base")
            
            # Detect query type
            query_type = self.detect_query_type(query)
            
            # Select appropriate system prompt based on query type
            if query_type == "procedural":
                system_prompt = self.PROCEDURAL_SYSTEM_PROMPT
                logger.info("Using procedural system prompt")
            else:
                system_prompt = self.DEFAULT_SYSTEM_PROMPT
                logger.info("Using default system prompt")
            
            # Update the system message with the appropriate prompt
            self.conversation_manager.clear_history(preserve_system_message=False)
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
            messages = self.conversation_manager.get_history()
            
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
                'messages': messages,
                'temperature': self.temperature,
                'top_p': self.top_p,
                'stream': True
            }
            if self.deployment_name == CHAT_DEPLOYMENT_O4_MINI:
                request["max_completion_tokens"] = self.max_completion_tokens
            else:
                request["max_completion_tokens"] = self.max_completion_tokens
                
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
            
            # Filter cited sources
            cited_raw = self._filter_cited(collected_answer, src_map)
            
            # Renumber in cited order: 1, 2, 3…
            renumber_map = {}
            cited_sources = []
            for new_id, src in enumerate(cited_raw, 1):
                old_id = src["id"]
                renumber_map[old_id] = str(new_id)
                entry = {
                    "id": str(new_id), 
                    "title": src["title"], 
                    "content": src["content"],
                    "parent_id": src.get("parent_id", ""),  # Include parent_id in cited sources
                    "is_procedural": src.get("is_procedural", False)
                }
                if "url" in src:
                    entry["url"] = src["url"]
                cited_sources.append(entry)
            
            # Apply renumbering to the answer
            for old, new in renumber_map.items():
                collected_answer = re.sub(rf"\[{old}\]", f"[{new}]", collected_answer)
            
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
            logger.error("RAG streaming error: %s", exc)
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
    rag_assistant = FlaskRAGAssistant()
    
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
    rag_assistant = FlaskRAGAssistant()
    
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


def run_phase3_tests():
    """Run all Phase 3 tests"""
    checkpoint_logger.info("Running Phase 3 tests")
    
    tests = [
        test_query_type_detection,
        test_prompt_selection
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
