  """
  Simple Redis-Backed RAG Assistant (No Intelligence)
  - Always: retrieves last N turns from Redis
  - Always: searches knowledge base
  - Combines history + KB context with basic formatting
  - Responds, stores Q&A in Redis
  - No query classification, no conversation intelligence, no routing
  """

  import os
  from typing import List, Tuple, Dict, Any, Optional, Union
  from services.session_memory import (
      SessionMemory,
      PostgresSessionMemory,
      RedisSessionMemory,
  )
  import re
  from openai_service import OpenAIService
  from azure.search.documents import SearchClient
  from azure.search.documents.models import VectorizedQuery
  from azure.core.credentials import AzureKeyCredential
  from config import (
      AZURE_OPENAI_ENDPOINT as OPENAI_ENDPOINT,
      AZURE_OPENAI_KEY as OPENAI_KEY,
      AZURE_OPENAI_API_VERSION as OPENAI_API_VERSION,
      CHAT_DEPLOYMENT_GPT4o as CHAT_DEPLOYMENT,
      EMBEDDING_DEPLOYMENT,
      AZURE_SEARCH_SERVICE as SEARCH_ENDPOINT,
      AZURE_SEARCH_INDEX as SEARCH_INDEX,
      AZURE_SEARCH_KEY as SEARCH_KEY,
      VECTOR_FIELD,
  )
  import json
  import time
  import hashlib

  from services.session_citation_registry import SessionCitationRegistry

  # --------- Advanced RAG Logic borrowed & adapted from rag_assistant_v2.py --------- #


  def chunk_document(text: str, max_chunk_size: int = 1000) -> List[str]:
      if len(text) <= max_chunk_size:
          return [text]
      sections = re.split(
          r"((?:^|\n)(?:#+\s+[^\n]+|\d+\.\s+[^\n]+|[A-Z][^\n:]{5,40}:))",
          text,
          flags=re.MULTILINE,
      )
      chunks = []
      current_chunk = ""
      current_headers = []
      for i, section in enumerate(sections):
          if not section.strip():
              continue
          if re.match(
              r"(?:^|\n)(?:#+\s+[^\n]+|\d+\.\s+[^\n]+|[A-Z][^\n:]{5,40}:)",
              section,
              flags=re.MULTILINE,
          ):
              current_headers.append(section.strip())
          elif i > 0:
              if len(current_chunk) + len(section) > max_chunk_size:
                  full_chunk = " ".join(current_headers) + " " + current_chunk
                  chunks.append(full_chunk)
                  current_chunk = section
              else:
                  current_chunk += section
      if current_chunk:
          full_chunk = " ".join(current_headers) + " " + current_chunk
          chunks.append(full_chunk)
      if not chunks:
          for i in range(0, len(text), max_chunk_size):
              chunks.append(text[i : i + max_chunk_size])
      return chunks


  def extract_metadata(chunk: str) -> Dict[str, Any]:
      metadata = {}
      metadata["is_procedural"] = bool(re.search(r"\d+\.\s+", chunk))
      if re.search(r"^#+\s+", chunk):
          heading_match = re.search(r"^(#+)\s+", chunk)
          metadata["section_level"] = len(heading_match.group(1)) if heading_match else 0
      step_numbers = re.findall(r"(\d+)\.\s+", chunk)
      if step_numbers:
          metadata["steps"] = [int(num) for num in step_numbers]
          metadata["first_step"] = min(metadata["steps"])
          metadata["last_step"] = max(metadata["steps"])
      metadata["is_procedure_start"] = bool(
          re.search(r"(?:how to|steps to|procedure for|guide to)", chunk.lower())
          and metadata.get("is_procedural", False)
      )
      return metadata


  def retrieve_with_hierarchy(results: List[Dict]) -> List[Dict]:
      parent_docs = {}
      for result in results:
          parent_id = result.get("parent_id", "")
          if parent_id and parent_id not in parent_docs:
              parent_docs[parent_id] = result.get("relevance", 0.0)
      ordered_results = []
      for parent_id, score in sorted(
          parent_docs.items(), key=lambda x: x[1], reverse=True
      )[:3]:
          parent_chunks = [r for r in results if r.get("parent_id", "") == parent_id]
          for chunk in parent_chunks:
              chunk["metadata"] = extract_metadata(chunk.get("chunk", ""))
          ordered_results.extend(parent_chunks)
      if not ordered_results:
          return results
      return ordered_results


  def prioritize_procedural_content(results: List[Dict]) -> List[Dict]:
      for result in results:
          if "metadata" not in result:
              result["metadata"] = extract_metadata(result.get("chunk", ""))
      procedural_results = []
      informational_results = []
      for result in results:
          if result.get("metadata", {}).get("is_procedural", False):
              procedural_results.append(result)
          else:
              informational_results.append(result)
      procedural_results.sort(key=lambda x: x.get("metadata", {}).get("first_step", 999))
      return procedural_results + informational_results


  def format_context_text(text: str) -> str:
      sentences = re.split(r"(?<=[.!?])\s+", text.strip())
      formatted = "\n\n".join(sentence for sentence in sentences if sentence)
      formatted = re.sub(r"(?<=\n\n)([A-Z][^\n:]{5,40})(?=\n\n)", r"**\1**", formatted)
      formatted = re.sub(r"(\d+\.\s+)", r"\n\1", formatted)
      return formatted


  def format_procedural_context(text: str) -> str:
      text = re.sub(r"(\d+\.\s+)", r"\n\1", text)
      text = re.sub(r"(\•\s+)", r"\n\1", text)
      text = re.sub(r"([A-Z][^\n:]{5,40}:)", r"\n**\1**\n", text)
      paragraphs = text.split("\n\n")
      formatted = "\n\n".join(p.strip() for p in paragraphs if p.strip())
      return formatted


  def is_procedural_content(text: str) -> bool:
      if re.search(r"\d+\.\s+[A-Z]", text):
          return True
      instructional_keywords = ["follow", "steps", "procedure", "instructions", "guide"]
      if any(keyword in text.lower() for keyword in instructional_keywords):
          return True
      return False


  def generate_unique_source_id(content: str = "", timestamp: float = None) -> str:
      if timestamp is None:
          timestamp = int(time.time() * 1000)
      hash_input = f"{content}_{timestamp}".encode("utf-8")
      content_hash = hashlib.md5(hash_input).hexdigest()[:8]
      unique_id = f"S_{timestamp}_{content_hash}"
      return unique_id


  # --------- System Prompts --------- #
  DEFAULT_SYSTEM_PROMPT = """
  You are a helpful RAG assistant for enterprise technical support.
  Always ground your answers in the provided knowledge base context and include inline citations in the format [1], [2], etc. whenever you reference information from the context or sources.

  Guidelines:
  - Every factual detail from the KB/context must be cited with an inline [n] marker, referencing the source order as given.
  - Do not make statements or claims that cannot be backed by the cited sources.
  - Include only new citations [n] in every response, including all follow-up questions, as long as the information is grounded in the KB context.
  - If you don't know the answer, state so clearly.
  - Respond in the same language as the user query.
  - If the context is unreadable or malformed, notify the user and stop.


  Example:
  "Product X improves workflow efficiency by 15% [1]. The recommended setup is as follows [2]: ..."

  If you cannot find the answer in the context, say "No source found."

  <context>
  {{CONTEXT}}
  </context>
  <user_query>
  {{QUERY}}
  </user_query>
  """
  PROCEDURAL_SYSTEM_PROMPT = """
  You are a helpful RAG assistant for enterprise procedural support.
  Always structure procedures as clear, numbered steps. Ground each instruction in the provided context and include [1], [2], etc. citation markers at the end of any step (or bullet) that is based on the KB/context.

  Guidelines:
  - Steps should be in logical order with all details needed for accuracy.
  - Citations [n] should map to the order of the knowledge base entries as provided.
  - Every important step or claim must include a citation as [n] after the step.
  - Maintain section headers for clarity if present in the source.
  - If you don't know the answer, state so.
  - When the user asks for more information on any [n], directly (e.g.: "What is step 3?"), or indirectly (e.g.:"Please elaborate on 1.";"Tell me more about 6"), you will alwy assume the user sking about the  provide the full context of that step, including all citations.

  Example procedure:
  1. Open the main interface [1].
  2. Click "Start Configuration" [1].
  3. Enter required values as described [2].

  <context>
  {{CONTEXT}}
  </context>
  <user_query>
  {{QUERY}}
  </user_query>
  """


  class EnhancedSimpleRedisRAGAssistant:
      def __init__(
          self,
          session_id: str,
          max_history: int = 5,
          memory: Optional[SessionMemory] = None,
      ):
          self.session_id = session_id
          self.max_history = max_history
          self.memory = memory or PostgresSessionMemory(max_turns=max_history)
          self.citation_registry = SessionCitationRegistry()
          self.openai_svc = OpenAIService(
              azure_endpoint=OPENAI_ENDPOINT,
              api_key=OPENAI_KEY,
              api_version=OPENAI_API_VERSION,
              deployment_name=CHAT_DEPLOYMENT,
          )
          from openai import AzureOpenAI

          self.embeddings_client = AzureOpenAI(
              azure_endpoint=OPENAI_ENDPOINT,
              api_key=OPENAI_KEY,
              api_version=OPENAI_API_VERSION,
          )
          self.search_client = SearchClient(
              endpoint=f"https://{SEARCH_ENDPOINT}.search.windows.net",
              index_name=SEARCH_INDEX,
              credential=AzureKeyCredential(SEARCH_KEY),
          )

      def _make_embedding(self, text: str) -> Optional[List[float]]:
          try:
              resp = self.embeddings_client.embeddings.create(
                  model=EMBEDDING_DEPLOYMENT,
                  input=text.strip(),
              )
              embedding = resp.data[0].embedding
              print(f"EMBEDDING DEBUG: type={type(embedding)}, len={len(embedding)}")
              print(f"EMBEDDING DEBUG: resp.data has {len(resp.data)} item(s)")
              if len(resp.data) != 1:
                  print(
                      "EMBEDDING DEBUG WARNING: resp.data contains multiple embeddings! This may cause dimensionality errors."
                  )
              return embedding
          except Exception:
              return None

      def _search_kb(self, query: str) -> List[Dict]:
          q_vec = self._make_embedding(query)
          if not q_vec:
              return []
          vec_q = self.search_client.search(
              search_text=query,
              vector_queries=[
                  VectorizedQuery(
                      vector=q_vec, k_nearest_neighbors=8, fields=VECTOR_FIELD
                  )
              ],
              select=["chunk", "title", "parent_id"],
              top=8,
          )
          results = [
              {
                  "chunk": r.get("chunk", ""),
                  "title": r.get("title", "Untitled"),
                  "parent_id": r.get("parent_id", ""),
                  "relevance": 1.0,
              }
              for r in list(vec_q)
          ]
          # Organize/prioritize procedural content for context window efficiency
          ordered = retrieve_with_hierarchy(results)
          prioritized = prioritize_procedural_content(ordered)
          return prioritized[:5]

      def _compile_history_context(self, history: List[Tuple[str, str]]) -> str:
          turns = []
          for user, assistant in history:
              if user:
                  turns.append(f"**User:** {user}")
              if assistant:
                  turns.append(f"**Assistant:** {assistant}")
          return "\n\n".join(turns)

      def _compile_kb_context_sections(self, kb_chunks: List[Dict]) -> str:
          # Format context with procedural/section awareness (advanced, taken from v2)
          entries = []
          for r in kb_chunks:
              chunk = r["chunk"].strip()
              if is_procedural_content(chunk):
                  formatted = format_procedural_context(chunk)
              else:
                  formatted = format_context_text(chunk)
              entries.append(formatted)
          return "\n\n".join(entries)

      def _select_system_prompt(self, kb_chunks: List[Dict], user_query: str) -> str:
          # Simple procedural detection: use procedural prompt if query or chunk suggests
          if any(
              is_procedural_content(r["chunk"]) for r in kb_chunks
          ) or is_procedural_content(user_query):
              return PROCEDURAL_SYSTEM_PROMPT
          return DEFAULT_SYSTEM_PROMPT

      def _convert_citations_to_links(
          self, answer: str, citations: list, message_id: str
      ) -> str:
          """
          Replace all ``[n]`` markdown citation markers in the answer with clickable
          HTML hyperlinks using the ``session-citation-link`` class expected by
          ``session-citation-system.js``. This includes cases where ``[n]`` is
          adjacent to text, punctuation or at line ends. The data attributes and
          link ``href``/``id`` will match ``session-citation-system`` expectations.

          The substitution is idempotent – running this method multiple times will
          not re-wrap already converted citation anchors. A simple negative
          lookbehind/ahead pattern is used to avoid matching links that were
          previously processed.

          This version avoids variable-width look-behind to prevent regex errors in
          Python.
          """

          def repl(match):
              idx = match.group(1)
              # Output all possible frontend-expected attributes and explicit inline onclick
              return (
                  f'<a href="javascript:void(0);" '
                  f'class="session-citation-link text-blue-600 hover:text-blue-800" '
                  f'data-citation-id="{idx}" '
                  f'onclick="handleSessionCitationClick({idx})">[{idx}]</a>'
              )

          result = answer

          # Pre-clean any '[n]ref=' or similar LLM hallucinations
          result = re.sub(r"\[(\d+)\]ref=[^\]\s]+", r"[\1]", result)
          result = re.sub(r"\[(\d+)\]href=[^\]\s]+", r"[\1]", result)

          # 1. Replace [n] at the start of a line (including start of text)
          result = re.sub(r"^\[(\d+)\]$", repl, result, flags=re.MULTILINE)
          # 2. Replace [n] after specific allowed characters (no alternation)
          result = re.sub(r"(?<=[\s\)\]\>\.,;:\"'\-_/])\[(\d+)\]", repl, result)
          # 3. Paranoia pass: any stray [n] not already converted (avoid nested anchors)
          result = re.sub(r"(?<!>)\[(\d+)\]", repl, result)
  
         
          return result

      def _rebuild_citation_map(self, cited_sources):
          """
          Maintain a cumulative map of all sources ever shown/cited in this session,
          so the frontend can resolve citation hyperlinks from any previous message.
          """
          if not hasattr(self, "_display_ordered_citation_map"):
              self._display_ordered_citation_map = {}
          for source in cited_sources:
              uid = source.get("id")
              if uid and uid not in self._display_ordered_citation_map:
                  self._display_ordered_citation_map[uid] = source

      def generate_response(self, user_query: str) -> Tuple[str, list]:
          """
          Returns: (html_answer, citations)
          'citations' is a list of dicts matching the [1..N] order used by the system prompt,
          suitable for sidebar or downstream application.
          """
          # 1. Retrieve history from Redis
          history = self.memory.get_history(
              self.session_id, last_n_turns=self.max_history
          )

          print(f"[DEBUG] User query: {user_query}")

          # 2. Search the KB
          kb_chunks = self._search_kb(user_query)
          print(f"[DEBUG] KB Chunks Retrieved: {len(kb_chunks)}")
          for idx, chunk in enumerate(kb_chunks, 1):
              print(
                  f"[DEBUG] KB Chunk {idx}: title={chunk.get('title')}, parent_id={chunk.get('parent_id')}, content_snippet={chunk.get('chunk','')[:80]}"
              )

          # 3. Compile the context string (history + KB in advanced format)
          history_section = self._compile_history_context(history)
          kb_section = self._compile_kb_context_sections(kb_chunks)
          sys_prompt = self._select_system_prompt(kb_chunks, user_query)
          context = ""
          if history_section:
              context += f"### Previous Conversation:\n{history_section}\n\n"
          if kb_section:
              context += f"### New Search Results:\n{kb_section}\n\n"

          # 4. Send to LLM (OpenAIService)
          messages = [
              {"role": "system", "content": sys_prompt},
              {"role": "user", "content": context + f"\n\nUser question: {user_query}"},
          ]
          answer = self.openai_svc.get_chat_response(
              messages=messages, max_completion_tokens=900
          )
          print(f"[DEBUG] LLM Answer: {answer[:500]}")

          # -- Citation assembly: Each kb_chunk corresponds to a [n] marker --
          citations = []
          for idx, chunk in enumerate(kb_chunks, 1):
              title = chunk.get("title") or f"Source {idx}"
              citations.append(
                  {
                      "index": idx,
                      "display_id": str(idx),
                      "title": title,
                      "content": chunk.get("chunk", ""),
                      "parent_id": chunk.get("parent_id", ""),
                      "id": f"source_{idx}",
                  }
              )
          print(f"[DEBUG] Citations Assembled: {len(citations)}")
          for c in citations:
              print(f"[DEBUG] Citation: {c}")

          # -- Register sources with session citation registry --
          registered_sources = self.citation_registry.register_sources(
              self.session_id, citations
          )
          print(f"[DEBUG] Registered Sources: {registered_sources}")

          # Use the registered sources with their assigned citation IDs
          for i, source in enumerate(registered_sources):
              if "citation_id" in source:
                  citations[i]["citation_id"] = source["citation_id"]
                  citations[i]["display_id"] = str(source["citation_id"])

          # --- Convert citations in answer to HTML links ---
          # Use a unique message_id for the citation links (e.g., session_id + timestamp)
          message_id = f"{self.session_id}_{int(time.time() * 1000)}"
          answer_with_links = self._convert_citations_to_links(
              answer, citations, message_id
          )
          print(f"[DEBUG] Answer with citation links: {answer_with_links[:500]}")

          # Store the turn in Redis
          summary_text = f"User: {user_query}\nAssistant: {answer_with_links}"
          summary = self.openai_svc.summarize_text(summary_text)
          self.memory.store_turn(self.session_id, user_query, answer_with_links, summary)

          # Return the answer with links and the registered sources
          return answer_with_links, registered_sources

      def stream_rag_response(self, user_query: str):
          """
          Stream partial answer content as it is generated by the LLM.
          After streaming, stores the completed answer in Redis.
          Ensures that all streamed chunks contain citation links (never raw [n]) after citation registration.
          """
          # 1. Retrieve history from Redis
          history = self.memory.get_history(
              self.session_id, last_n_turns=self.max_history
          )

          # 2. Search the KB
          kb_chunks = self._search_kb(user_query)

          # 3. Compile the context string (history + KB in advanced format)
          history_section = self._compile_history_context(history)
          kb_section = self._compile_kb_context_sections(kb_chunks)
          sys_prompt = self._select_system_prompt(kb_chunks, user_query)
          context = ""
          if history_section:
              context += f"### Previous Conversation:\n{history_section}\n\n"
          if kb_section:
              context += f"### New Search Results:\n{kb_section}\n\n"

          messages = [
              {"role": "system", "content": sys_prompt},
              {"role": "user", "content": context + f"\n\nUser question: {user_query}"},
          ]

          # 4a. Prepare citation metadata before streaming
          citations = []
          for idx, chunk in enumerate(kb_chunks, 1):
              title = chunk.get("title") or f"Source {idx}"
              citations.append(
                  {
                      "index": idx,
                      "display_id": str(idx),
                      "title": title,
                      "content": chunk.get("chunk", ""),
                      "parent_id": chunk.get("parent_id", ""),
                      "id": f"source_{idx}",
                  }
              )

          # Register sources with session citation registry (once per streamed message)
          registered_sources = self.citation_registry.register_sources(
              self.session_id, citations
          )
          # Use the registered sources with their assigned citation IDs
          for i, source in enumerate(registered_sources):
              if "citation_id" in source:
                  citations[i]["citation_id"] = source["citation_id"]
                  citations[i]["display_id"] = str(source["citation_id"])

          # Emit metadata event FIRST so frontend can associate citation IDs
          yield {"sources": registered_sources}

          # Stream from OpenAIService and post-process citation links in-stream
          # Use a stable message_id for the links (session + ms timestamp at stream start)
          import time

          message_id = f"{self.session_id}_{int(time.time() * 1000)}"

          # We buffer up to each chunk then compute the linked HTML, yielding only the DELTA to not resend content
          full_answer = ""
          last_yielded = 0
          for chunk in self.openai_svc.get_chat_response_stream(
              messages=messages, max_completion_tokens=900
          ):
              full_answer += chunk
              # Always convert all [n] in full_answer-so-far to citation links with known citations/message_id
              answer_with_links = self._convert_citations_to_links(
                  full_answer, citations, message_id
              )
              # Yield only the new stuff (i.e., skipping any previously yielded portion)
              new_content = answer_with_links[last_yielded:]
              if new_content:
                  yield new_content
                  last_yielded = len(answer_with_links)
          # 5. Store the fully linked answer using session memory backend
          final_answer = self._convert_citations_to_links(
              full_answer, citations, message_id
          )
          summary = self.openai_svc.summarize_text(
              f"User: {user_query}\nAssistant: {final_answer}"
          )
          self.memory.store_turn(self.session_id, user_query, final_answer, summary)

      def clear_conversation_history(self) -> None:
          """Clear conversation history for this session"""
          self.memory.clear(self.session_id)
          # Also clear the citation map
          if hasattr(self, "_display_ordered_citation_map"):
              self._display_ordered_citation_map = {}

      def get_cache_stats(self) -> Dict[str, Any]:
          """Get basic cache statistics"""
          history = self.memory.get_history(
              self.session_id, last_n_turns=100
          )  # Get all history
          stats = {
              "session_id": self.session_id,
              "conversation_turns": len(history),
              "citation_map_size": len(
                  getattr(self, "_display_ordered_citation_map", {})
              ),
          }
          stats.update(self.memory.get_stats())
          return stats

      def clear_cache(self, cache_type: str = None) -> bool:
          """Clear cache (same as clear conversation history for this implementation)"""
          try:
              self.clear_conversation_history()
              return True
          except Exception:
              return False
