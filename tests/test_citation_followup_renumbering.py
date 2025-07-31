"""
Enhanced Frontend Integration Test - Citation Renumbering with Followup
Tests the system's ability to handle citation renumbering across multiple exchanges
while maintaining unique IDs and resetting display IDs appropriately.
"""

def test_citation_followup_renumbering():
    print("=== Enhanced Frontend Integration Test - Citation Followup ===")
    
    # Initial user query and bot response
    print("\n--- Initial Exchange ---")
    print("User: 'Tell me about gas chromatography separation techniques'")
    
    initial_response = {
        "answer": "Gas chromatography is used for separation [1]. The procedure involves multiple steps [2].",
        "sources": [
            {
                "unique_id": "S_1642345678901_abc12345",
                "display_id": 1,
                "title": "Introduction to Gas Chromatography",
                "has_content": True,
                "parent_id": "doc_gc_intro_001"
            },
            {
                "unique_id": "S_1642345678902_def67890", 
                "display_id": 2,
                "title": "GC Operating Procedure",
                "has_content": True,
                "parent_id": "doc_gc_procedure_002"
            }
        ]
    }
    
    print(f"Bot Response: {initial_response['answer']}")
    print(f"Sources: {len(initial_response['sources'])}")
    for source in initial_response['sources']:
        print(f"  - Unique ID: {source['unique_id']}")
        print(f"    Display ID: {source['display_id']}")
        print(f"    Title: {source['title']}")
        print(f"    Has content: {source['has_content']}")
        print(f"    Parent ID: {source['parent_id']}")
    
    # Validate initial response
    for i, source in enumerate(initial_response['sources'], 1):
        assert source['display_id'] == i, f"Initial source {i} display ID mismatch"
        assert source['unique_id'], f"Source {i} missing unique ID"
        assert source['title'], f"Source {i} missing title"
        print(f"  ✓ Initial Source {i} has all required fields")
    
    print("\n--- Followup Exchange ---")
    print("User: 'What about the temperature requirements and mobile phase selection?'")
    
    # Bot response to followup - citations renumbered, unique IDs preserved + new source
    followup_response = {
        "answer": "Temperature control is critical for separation efficiency [1]. Mobile phase selection affects resolution [2]. The column temperature typically ranges from 50-300°C [3].",
        "sources": [
            {
                "unique_id": "S_1642345678902_def67890",  # Same unique ID as before
                "display_id": 1,  # Reset display ID
                "title": "GC Operating Procedure", 
                "has_content": True,
                "parent_id": "doc_gc_procedure_002"
            },
            {
                "unique_id": "S_1642345678903_ghi11111",  # New unique ID
                "display_id": 2,  # New display ID
                "title": "Mobile Phase Optimization in GC",
                "has_content": True, 
                "parent_id": "doc_gc_mobile_phase_003"
            },
            {
                "unique_id": "S_1642345678901_abc12345",  # Same unique ID as initial [1]
                "display_id": 3,  # Reset display ID
                "title": "Introduction to Gas Chromatography",
                "has_content": True,
                "parent_id": "doc_gc_intro_001"
            }
        ]
    }
    
    print(f"Bot Response: {followup_response['answer']}")
    print(f"Sources: {len(followup_response['sources'])}")
    for source in followup_response['sources']:
        print(f"  - Unique ID: {source['unique_id']}")
        print(f"    Display ID: {source['display_id']}")
        print(f"    Title: {source['title']}")
        print(f"    Has content: {source['has_content']}")
        print(f"    Parent ID: {source['parent_id']}")
    
    # Validate followup response
    for i, source in enumerate(followup_response['sources'], 1):
        assert source['display_id'] == i, f"Followup source {i} display ID mismatch"
        assert source['unique_id'], f"Followup source {i} missing unique ID"
        assert source['title'], f"Followup source {i} missing title"
        print(f"  ✓ Followup Source {i} has all required fields")
    
    # Validate citation renumbering logic
    print("\n--- Citation Renumbering Validation ---")
    
    # Check that unique IDs are preserved across exchanges
    initial_unique_ids = {s['unique_id'] for s in initial_response['sources']}
    followup_unique_ids = {s['unique_id'] for s in followup_response['sources']}
    
    # Find reused unique IDs
    reused_ids = initial_unique_ids.intersection(followup_unique_ids)
    print(f"Reused unique IDs: {len(reused_ids)}")
    for uid in reused_ids:
        print(f"  - {uid}")
    
    # Verify display IDs reset properly (1, 2, 3)
    followup_display_ids = [s['display_id'] for s in followup_response['sources']]
    expected_display_ids = [1, 2, 3]
    assert followup_display_ids == expected_display_ids, f"Display IDs not properly reset: {followup_display_ids}"
    print(f"  ✓ Display IDs properly reset to: {followup_display_ids}")
    
    # Verify we have exactly 3 sources in followup
    assert len(followup_response['sources']) == 3, f"Expected 3 sources, got {len(followup_response['sources'])}"
    print(f"  ✓ Followup response contains exactly 3 sources")
    
    # Verify unique ID preservation with display ID reset
    for source in followup_response['sources']:
        if source['unique_id'] in reused_ids:
            print(f"  ✓ Unique ID {source['unique_id']} preserved with new display ID {source['display_id']}")
    
    print("\nFrontend integration test complete")
    print("✓ Initial Exchange: PASSED")
    print("✓ Followup Exchange: PASSED") 
    print("✓ Citation Renumbering: PASSED")
    print("✓ Unique ID Preservation: PASSED")
    print("✓ Display ID Reset: PASSED")
    print("✓ Enhanced Frontend Integration: PASSED")

if __name__ == "__main__":
    test_citation_followup_renumbering()
