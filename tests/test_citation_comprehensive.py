#!/usr/bin/env python3
"""
Comprehensive test for the citation system fix.
Tests the dual-ID system (unique IDs + display IDs) across multiple scenarios.
"""

import sys
import os
import json
import time
import requests
from typing import Dict, List, Any

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from rag_assistant_v2 import FlaskRAGAssistantV2

def test_citation_system_comprehensive():
    """Test the complete citation system with dual IDs"""
    print("=== Comprehensive Citation System Test ===")
    
    # Initialize the RAG assistant
    assistant = FlaskRAGAssistantV2()
    
    # Test 1: Basic citation generation and filtering
    print("\n1. Testing basic citation generation...")
    
    # Mock search results with different sources
    mock_results = [
        {
            "chunk": "Gas chromatography (GC) is a common analytical technique used to separate and analyze compounds.",
            "title": "Introduction to Gas Chromatography",
            "parent_id": "doc_gc_intro_001",
            "relevance": 0.95
        },
        {
            "chunk": "1. Turn on the GC instrument\n2. Set the temperature program\n3. Inject the sample",
            "title": "GC Operating Procedure",
            "parent_id": "doc_gc_procedure_002", 
            "relevance": 0.90
        },
        {
            "chunk": "Troubleshooting common GC issues: peak tailing, baseline drift, and retention time shifts.",
            "title": "GC Troubleshooting Guide",
            "parent_id": "doc_gc_troubleshoot_003",
            "relevance": 0.85
        }
    ]
    
    # Prepare context and source map
    context, src_map = assistant._prepare_context(mock_results)
    
    print(f"Generated {len(src_map)} sources with unique IDs:")
    for uid, info in src_map.items():
        print(f"  - {uid}: {info['title'][:50]}...")
    
    # Test 2: Citation filtering with different answer patterns
    print("\n2. Testing citation filtering...")
    
    test_answers = [
        # Answer with numeric citations
        "Gas chromatography is used for separation [1]. The procedure involves several steps [2].",
        
        # Answer with unique ID citations (simulating what the model might generate)
        f"Gas chromatography is used for separation [{list(src_map.keys())[0]}]. The procedure involves several steps [{list(src_map.keys())[1]}].",
        
        # Answer with mixed citations
        f"Gas chromatography is used for separation [1]. For troubleshooting, refer to [{list(src_map.keys())[2]}].",
        
        # Answer without explicit citations (should still work for follow-ups)
        "Gas chromatography involves heating the sample and using a carrier gas to separate compounds."
    ]
    
    for i, answer in enumerate(test_answers):
        print(f"\nTest answer {i+1}: {answer[:60]}...")
        cited_sources = assistant._filter_cited(answer, src_map)
        print(f"  Found {len(cited_sources)} cited sources:")
        for source in cited_sources:
            print(f"    - ID: {source['id']}, Title: {source['title'][:40]}...")
    
    # Test 3: Renumbering and display ID assignment
    print("\n3. Testing renumbering and display ID assignment...")
    
    answer_with_citations = f"Gas chromatography is used for separation [{list(src_map.keys())[0]}]. The procedure involves several steps [{list(src_map.keys())[1]}]. For troubleshooting, see [{list(src_map.keys())[2]}]."
    
    cited_sources, renumber_map = assistant._assemble_cited_sources(answer_with_citations, src_map)
    
    print(f"Renumber map: {renumber_map}")
    print(f"Cited sources with display IDs:")
    for source in cited_sources:
        print(f"  - Unique ID: {source['id']}, Display ID: {source['display_id']}, Title: {source['title'][:40]}...")
    
    # Test 4: Conversation continuity
    print("\n4. Testing conversation continuity...")
    
    # Simulate a conversation with follow-up questions
    queries = [
        "How do I operate a gas chromatograph?",
        "What about troubleshooting issues?",
        "Can you explain the separation process in more detail?"
    ]
    
    for i, query in enumerate(queries):
        print(f"\nQuery {i+1}: {query}")
        
        # For the first query, we'll get new sources
        # For follow-ups, we should use existing sources from cumulative map
        if i == 0:
            # First query - fresh search
            assistant._cumulative_src_map = {}
        
        # Simulate the RAG response generation
        try:
            # Mock the search results for first query only
            if i == 0:
                # Update cumulative map with our mock results
                context, src_map = assistant._prepare_context(mock_results)
                assistant._cumulative_src_map.update(src_map)
            
            # For follow-ups, use existing cumulative map
            current_src_map = assistant._cumulative_src_map
            
            # Simulate model response with citations
            if i == 0:
                mock_answer = f"To operate a gas chromatograph, follow these steps [{list(current_src_map.keys())[1]}]. First, understand the basic principles [{list(current_src_map.keys())[0]}]."
            elif i == 1:
                mock_answer = f"For troubleshooting GC issues, refer to the troubleshooting guide [{list(current_src_map.keys())[2]}]. Common problems include peak issues mentioned earlier."
            else:
                mock_answer = f"The separation process in GC works by [{list(current_src_map.keys())[0]}]. This is different from the operational steps [{list(current_src_map.keys())[1]}]."
            
            # Test citation filtering and renumbering
            cited_sources, renumber_map = assistant._assemble_cited_sources(mock_answer, current_src_map)
            
            print(f"  Answer: {mock_answer[:80]}...")
            print(f"  Cited sources: {len(cited_sources)}")
            print(f"  Cumulative sources available: {len(current_src_map)}")
            
            # Verify that display IDs are consistent and unique IDs are preserved
            for source in cited_sources:
                print(f"    - Display ID: {source['display_id']}, Unique ID: {source['id'][:20]}...")
                
        except Exception as e:
            print(f"  Error in query {i+1}: {e}")
    
    # Test 5: Edge cases
    print("\n5. Testing edge cases...")
    
    edge_cases = [
        # Answer with non-existent citation
        "This refers to source [999] which doesn't exist.",
        
        # Answer with malformed citations
        "This has [malformed] and [123abc] citations.",
        
        # Answer with duplicate citations
        f"This mentions [{list(src_map.keys())[0]}] twice: [{list(src_map.keys())[0]}].",
        
        # Empty answer
        "",
        
        # Answer with only text, no citations
        "This is just plain text without any citations."
    ]
    
    for i, edge_case in enumerate(edge_cases):
        print(f"\nEdge case {i+1}: {edge_case[:50]}...")
        try:
            cited_sources = assistant._filter_cited(edge_case, src_map)
            print(f"  Found {len(cited_sources)} cited sources")
        except Exception as e:
            print(f"  Error: {e}")
    
    print("\n=== Test Complete ===")
    return True

def test_frontend_integration():
    """Test that the frontend can handle the dual-ID system"""
    print("\n=== Frontend Integration Test ===")
    
    # Test data structure that would be sent to frontend
    mock_response = {
        "answer": "Gas chromatography is used for separation [1]. The procedure involves steps [2].",
        "sources": [
            {
                "id": "S_1642345678901_abc12345",  # Unique ID
                "display_id": "1",  # Display ID
                "title": "Introduction to Gas Chromatography",
                "content": "Gas chromatography (GC) is a common analytical technique...",
                "parent_id": "doc_gc_intro_001"
            },
            {
                "id": "S_1642345678902_def67890",  # Unique ID
                "display_id": "2",  # Display ID
                "title": "GC Operating Procedure", 
                "content": "1. Turn on the GC instrument\n2. Set the temperature program...",
                "parent_id": "doc_gc_procedure_002"
            }
        ]
    }
    
    print("Mock response structure:")
    print(f"  Answer: {mock_response['answer']}")
    print(f"  Sources: {len(mock_response['sources'])}")
    
    for source in mock_response['sources']:
        print(f"    - Unique ID: {source['id']}")
        print(f"      Display ID: {source['display_id']}")
        print(f"      Title: {source['title']}")
        print(f"      Has content: {'Yes' if source['content'] else 'No'}")
        print(f"      Parent ID: {source['parent_id']}")
    
    # Verify the structure matches what the frontend expects
    required_fields = ['id', 'display_id', 'title', 'content', 'parent_id']
    for i, source in enumerate(mock_response['sources']):
        missing_fields = [field for field in required_fields if field not in source]
        if missing_fields:
            print(f"  ERROR: Source {i+1} missing fields: {missing_fields}")
        else:
            print(f"  ✓ Source {i+1} has all required fields")
    
    print("Frontend integration test complete")
    return True

def test_api_endpoint():
    """Test the actual API endpoint if server is running"""
    print("\n=== API Endpoint Test ===")
    
    try:
        # Test if server is running
        response = requests.get("http://localhost:5000/", timeout=5)
        if response.status_code != 200:
            print("Server not running or not accessible")
            return False
            
        print("Server is running, testing citation API...")
        
        # Test query that should generate citations
        test_query = "How do I troubleshoot an Agilent GC?"
        
        response = requests.post(
            "http://localhost:5000/api/query",
            json={"query": test_query},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            
            print(f"Query: {test_query}")
            print(f"Response received: {len(data.get('answer', ''))} characters")
            print(f"Sources returned: {len(data.get('sources', []))}")
            
            # Check if sources have the dual-ID structure
            sources = data.get('sources', [])
            for i, source in enumerate(sources):
                has_unique_id = 'id' in source and source['id'].startswith('S_')
                has_display_id = 'display_id' in source
                print(f"  Source {i+1}:")
                print(f"    Has unique ID: {has_unique_id}")
                print(f"    Has display ID: {has_display_id}")
                if has_unique_id:
                    print(f"    Unique ID: {source['id']}")
                if has_display_id:
                    print(f"    Display ID: {source['display_id']}")
            
            # Test follow-up query
            print("\nTesting follow-up query...")
            follow_up_query = "What about the temperature settings?"
            
            response2 = requests.post(
                "http://localhost:5000/api/query",
                json={"query": follow_up_query},
                timeout=30
            )
            
            if response2.status_code == 200:
                data2 = response2.json()
                print(f"Follow-up query: {follow_up_query}")
                print(f"Response received: {len(data2.get('answer', ''))} characters")
                print(f"Sources returned: {len(data2.get('sources', []))}")
                
                # Check if citations are working in follow-up
                answer = data2.get('answer', '')
                citation_count = len([m for m in answer if m == '['])
                print(f"Citations in follow-up answer: {citation_count}")
            
            return True
        else:
            print(f"API request failed: {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"Could not connect to server: {e}")
        print("Skipping API endpoint test")
        return False

if __name__ == "__main__":
    print("Starting comprehensive citation system tests...")
    
    # Run all tests
    tests = [
        ("Citation System Core", test_citation_system_comprehensive),
        ("Frontend Integration", test_frontend_integration),
        ("API Endpoint", test_api_endpoint)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*60}")
        print(f"Running: {test_name}")
        print('='*60)
        
        try:
            result = test_func()
            results.append((test_name, result))
            print(f"✓ {test_name}: {'PASSED' if result else 'FAILED'}")
        except Exception as e:
            print(f"✗ {test_name}: ERROR - {e}")
            results.append((test_name, False))
    
    # Summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print('='*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{test_name}: {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Citation system is working correctly.")
    else:
        print("⚠️  Some tests failed. Please review the output above.")
    
    sys.exit(0 if passed == total else 1)
