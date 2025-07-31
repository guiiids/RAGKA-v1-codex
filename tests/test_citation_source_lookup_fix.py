#!/usr/bin/env python3
"""
Test to verify that the citation source lookup fix works correctly.

This test simulates the exact scenario described:
1. First message gets sources with display IDs [1], [2], [3] 
2. Second message gets different sources, also with display IDs [1], [2], [3]
3. Citations from the first message should still be clickable and accessible
4. Citations are assembled per-message (no cross-contamination)
5. But ALL sources remain accessible for lookup (frontend compatibility)
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from rag_assistant_v2 import FlaskRAGAssistantV2
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_first_message_timing_fix():
    """Test the critical first message timing fix where sources appear but aren't clickable."""
    
    print("=== Testing First Message Timing Fix ===")
    
    # Create RAG assistant instance
    assistant = FlaskRAGAssistantV2()
    
    # Simulate first message with search results but "No relevant information found" answer
    print("\n1. Simulating first message timing issue...")
    first_src_map = {
        "S_1753296296005_74601655": {
            "title": "iLab Community_2312958.pdf",
            "content": "iLab Community documentation content...",
            "parent_id": "aHR0cHM6Ly9jYXBvenpvbDAyc3RvcmFnZS5ibG9iLmNvcmUud2luZG93cy5uZXQvc2FnZS1wcm9kLWRhdGFsYWtlL2lsYWJfaGVscGp1aWNlL2lMYWIlMjBDb21tdW5pdHlfMjMxMjk1OC5wZGY1",
            "is_procedural": True,
            "unique_id": "S_1753296296005_74601655"
        },
        "S_1753268569399_9b4f7551": {
            "title": "iLab API_958429.pdf",
            "content": "iLab API documentation content...",
            "parent_id": "aHR0cHM6Ly9jYXBvenpvbDAyc3RvcmFnZS5ibG9iLmNvcmUud2luZG93cy5uZXQvc2FnZS1wcm9kLWRhdGFsYWtlL2lsYWJfaGVscGp1aWNlL2lMYWIlMjBBUElfOTU4NDI5LnBkZg2",
            "is_procedural": True,
            "unique_id": "S_1753268569399_9b4f7551"
        },
        "S_1753268569403_19944585": {
            "title": "Key iLab Terms_261285.pdf",
            "content": "Key iLab terms and definitions...",
            "parent_id": "aHR0cHM6Ly9jYXBvenpvbDAyc3RvcmFnZS5ibG9iLmNvcmUud2luZG93cy5uZXQvc2FnZS1wcm9kLWRhdGFsYWtlL2lsYWJfaGVscGp1aWNlL0tleSUyMGlMYWIlMjBUZXJtc18yNjEyODUucGRm0",
            "is_procedural": False,
            "unique_id": "S_1753268569403_19944585"
        }
    }
    
    # Simulate first message answer with NO citations (like "No relevant information found")
    first_answer = "No relevant information found in the knowledge base."
    
    print(f"First message answer: {first_answer}")
    print(f"First message src_map has {len(first_src_map)} sources")
    
    # Process first message citations - this should trigger the fallback logic
    first_cited_sources, first_renumber_map = assistant._assemble_cited_sources(first_answer, first_src_map)
    assistant._rebuild_citation_map(first_cited_sources)
    
    print(f"First message cited sources after fallback: {len(first_cited_sources)}")
    for src in first_cited_sources:
        print(f"  [{src['display_id']}] {src['id']} -> {src['title']}")
    
    print(f"First message citation map size: {len(assistant._display_ordered_citation_map)}")
    
    # CRITICAL TEST: Sources should be created as fallback and accessible
    assert len(first_cited_sources) > 0, "First message should have fallback sources even with 'No relevant information found'"
    
    # Store first message source IDs for later lookup test
    first_message_source_ids = [src['id'] for src in first_cited_sources]
    print(f"First message source IDs: {first_message_source_ids}")
    
    # CRITICAL TEST: All sources from first message should be accessible in citation map
    for source_id in first_message_source_ids:
        assert source_id in assistant._display_ordered_citation_map, f"First message source {source_id} should be accessible for lookup"
        source_info = assistant._display_ordered_citation_map[source_id]
        print(f"  ✓ {source_id} -> {source_info['title']} (accessible for clicking)")
    
    # Simulate second message with successful citations
    print("\n2. Simulating second message with successful citations...")
    second_src_map = {
        "S_1753296403691_54fed2a4": {
            "title": "Agilent GC 8860 Site Preparation Checklist_ZH.pdf",
            "content": "Agilent CrossLab Start-Up **Agilent 8860 ** Agilent Technologies...",
            "parent_id": "aHR0cHM6Ly9jYXBvenpvbDAyc3RvcmFuZ2UuYmxvYi5jb3JlLndpbmRvd3MubmV0L3NhZ2UtcHJvZC1kYXRhbGFrZS9BZ2lsZW50JTIwR0MlMjA4ODYwJTIwU2l0ZSUyMFByZXBhcmF0aW9uJTIwQ2hlY2tsaXN0X1pILnBkZg2",
            "is_procedural": True,
            "unique_id": "S_1753296403691_54fed2a4"
        }
    }
    
    # Simulate second message answer with successful citations
    second_answer = "Agilent GC 8860 site preparation includes several steps [S_1753296403691_54fed2a4]."
    
    # Process second message citations
    second_cited_sources, second_renumber_map = assistant._assemble_cited_sources(second_answer, second_src_map)
    assistant._rebuild_citation_map(second_cited_sources)
    
    print(f"Second message cited sources: {len(second_cited_sources)}")
    for src in second_cited_sources:
        print(f"  [{src['display_id']}] {src['id']} -> {src['title']}")
    
    print(f"Total citation map size after second message: {len(assistant._display_ordered_citation_map)}")
    
    # CRITICAL TEST: First message sources should STILL be accessible after second message
    print("\n3. Testing persistent accessibility after second message...")
    
    for source_id in first_message_source_ids:
        assert source_id in assistant._display_ordered_citation_map, f"First message source {source_id} should STILL be accessible after second message"
        source_info = assistant._display_ordered_citation_map[source_id]
        print(f"  ✓ {source_id} -> {source_info['title']} (still accessible)")
    
    # Verify second message sources are also accessible
    second_message_source_ids = [src['id'] for src in second_cited_sources]
    for source_id in second_message_source_ids:
        assert source_id in assistant._display_ordered_citation_map, f"Second message source {source_id} should be accessible"
        source_info = assistant._display_ordered_citation_map[source_id]
        print(f"  ✓ {source_id} -> {source_info['title']} (accessible)")
    
    print("\n✅ First message timing fix is working correctly!")
    print("- First message sources appear in sidebar even with 'No relevant information found'")
    print("- All first message sources remain clickable")
    print("- Sources persist across subsequent messages")
    
    return True

def test_deduplication_scenario():
    """Test the specific deduplication scenario mentioned in the issue."""
    
    print("\n=== Testing Deduplication Scenario ===")
    
    assistant = FlaskRAGAssistantV2()
    
    # Simulate the exact scenario: 5 sources in source_map, but 2 are from same document
    src_map = {
        "S_1753268569399_9b4f7551": {
            "title": "iLab API_958429.pdf",
            "content": "First chunk from iLab API...",
            "parent_id": "ilab_api_parent_id", 
            "is_procedural": True
        },
        "S_1753268569400_395dfeae": {
            "title": "iLab Community_2312958.pdf",
            "content": "First chunk from iLab Community...",
            "parent_id": "ilab_community_parent_id",
            "is_procedural": True
        },
        "S_1753268569401_aa4626ce": {
            "title": "iLab Community_2312958.pdf",  # Same document as above
            "content": "Second chunk from iLab Community...",
            "parent_id": "ilab_community_parent_id",  # Same parent_id
            "is_procedural": True
        },
        "S_1753268569402_a8bb7b30": {
            "title": "iLab Community_2312958.pdf",  # Same document again
            "content": "Third chunk from iLab Community...",
            "parent_id": "ilab_community_parent_id",  # Same parent_id
            "is_procedural": True
        },
        "S_1753268569403_19944585": {
            "title": "Key iLab Terms_261285.pdf",
            "content": "Key terms content...",
            "parent_id": "ilab_terms_parent_id",
            "is_procedural": False
        }
    }
    
    # Test the deduplication function directly
    print(f"Original source map has {len(src_map)} sources")
    print("Sources by document:")
    for uid, src in src_map.items():
        print(f"  {uid} -> {src['title']} (parent: {src['parent_id'][:20]}...)")
    
    # Convert to the format expected by _deduplicate_by_document
    results = []
    for uid, src in src_map.items():
        results.append({
            "id": uid,
            "title": src["title"],
            "parent_id": src["parent_id"],
            "content": src["content"],
            "is_procedural": src["is_procedural"],
            "relevance": 0.8  # Mock relevance score
        })
    
    # Apply deduplication
    unique_results = assistant._deduplicate_by_document(results)
    
    print(f"\nAfter deduplication: {len(unique_results)} unique documents")
    print("Unique documents:")
    for result in unique_results:
        print(f"  {result['id']} -> {result['title']}")
    
    # Verify deduplication worked correctly
    assert len(unique_results) == 3, f"Expected 3 unique documents, got {len(unique_results)}"
    
    # Check that we have one entry per unique document
    unique_docs = set()
    for result in unique_results:
        doc_key = (result["title"], result["parent_id"])
        assert doc_key not in unique_docs, f"Document {doc_key} appears multiple times after deduplication"
        unique_docs.add(doc_key)
    
    print("  ✓ Deduplication working correctly - 5 sources -> 3 unique documents")
    
    # Now test citation assembly on the deduplicated results
    # Convert back to src_map format for citation processing
    deduplicated_src_map = {}
    for result in unique_results:
        deduplicated_src_map[result["id"]] = {
            "title": result["title"],
            "content": result["content"], 
            "parent_id": result["parent_id"],
            "is_procedural": result["is_procedural"]
        }
    
    # Simulate answer that references all unique documents
    answer_with_citations = "iLab API information [S_1753268569399_9b4f7551] and Community documentation [S_1753268569400_395dfeae] plus terms [S_1753268569403_19944585]."
    
    # Process citations
    cited_sources, renumber_map = assistant._assemble_cited_sources(answer_with_citations, deduplicated_src_map)
    
    print(f"\nCitation assembly results:")
    print(f"Cited sources: {len(cited_sources)}")
    for src in cited_sources:
        print(f"  [{src['display_id']}] {src['id']} -> {src['title']}")
    
    # Should have exactly 3 cited sources (one per unique document)
    assert len(cited_sources) == 3, f"Expected 3 cited sources, got {len(cited_sources)}"
    
    # Should be numbered [1], [2], [3]
    display_ids = [src['display_id'] for src in cited_sources]
    assert display_ids == ['1', '2', '3'], f"Expected display IDs [1, 2, 3], got {display_ids}"
    
    print("  ✓ Citation assembly working correctly - 3 citations for 3 unique documents")
    
    return True

if __name__ == "__main__":
    try:
        # Run the first message timing fix test (this is the critical one)
        test_first_message_timing_fix()
        
        # Run the deduplication scenario test  
        test_deduplication_scenario()
        
        print("\n🎉 ALL TESTS PASSED! The critical first message timing fix is working correctly.")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
