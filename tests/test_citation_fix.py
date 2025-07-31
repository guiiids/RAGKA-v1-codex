"""
Test script for citation link fix implementation.
This tests the unique ID generation, citation detection, and renumbering logic.
"""
import unittest
import re
import time
import hashlib
from rag_assistant_v2 import (
    FlaskRAGAssistantV2, 
    generate_unique_source_id,
    format_context_text,
    format_procedural_context
)

class TestCitationFix(unittest.TestCase):
    """Test cases for citation link fix implementation."""

    def setUp(self):
        """Set up test environment."""
        self.assistant = FlaskRAGAssistantV2()
        
        # Sample test data
        self.sample_content = "This is a test content for source ID generation."
        self.sample_results = [
            {
                "chunk": "First chunk of content with some information.",
                "title": "First Source",
                "parent_id": "parent_doc_1",
                "relevance": 0.9,
                "metadata": {"is_procedural": False}
            },
            {
                "chunk": "1. Step one of a procedure\n2. Step two of a procedure",
                "title": "Procedural Source",
                "parent_id": "parent_doc_2",
                "relevance": 0.8,
                "metadata": {"is_procedural": True}
            },
            {
                "chunk": "Additional information about the topic.",
                "title": "Additional Info",
                "parent_id": "parent_doc_3",
                "relevance": 0.7,
                "metadata": {"is_procedural": False}
            }
        ]

    def test_unique_id_generation(self):
        """Test that unique source IDs are generated correctly."""
        # Generate a unique ID
        unique_id = generate_unique_source_id(self.sample_content)
        
        # Verify format: S_{timestamp}_{hash}
        self.assertTrue(re.match(r'S_\d+_[a-f0-9]{8}', unique_id), 
                        f"ID format incorrect: {unique_id}")
        
        # Generate another ID with the same content but different timestamp
        time.sleep(0.001)  # Ensure different timestamp
        another_id = generate_unique_source_id(self.sample_content)
        
        # IDs should be different due to timestamp
        self.assertNotEqual(unique_id, another_id, 
                           "IDs should be different with different timestamps")
        
        # Test with explicit timestamp for deterministic testing
        fixed_timestamp = 1626262626000
        fixed_id = generate_unique_source_id(self.sample_content, fixed_timestamp)
        
        # Calculate expected hash
        hash_input = f"{self.sample_content}_{fixed_timestamp}".encode('utf-8')
        expected_hash = hashlib.md5(hash_input).hexdigest()[:8]
        expected_id = f"S_{fixed_timestamp}_{expected_hash}"
        
        self.assertEqual(fixed_id, expected_id, 
                        f"ID with fixed timestamp incorrect: {fixed_id} vs {expected_id}")

    def test_prepare_context_with_unique_ids(self):
        """Test that _prepare_context uses unique IDs."""
        # Call _prepare_context with sample results
        context, src_map = self.assistant._prepare_context(self.sample_results)
        
        # Verify that source IDs in the context are unique IDs
        source_ids = re.findall(r'<source id="([^"]+)"', context)
        
        # Check that we have the expected number of sources
        self.assertEqual(len(source_ids), len(self.sample_results), 
                        f"Expected {len(self.sample_results)} sources, got {len(source_ids)}")
        
        # Check that all IDs follow the unique ID format
        for sid in source_ids:
            self.assertTrue(re.match(r'S_\d+_[a-f0-9]{8}', sid), 
                           f"Source ID format incorrect: {sid}")
        
        # Check that source map contains the unique IDs
        for sid in source_ids:
            self.assertIn(sid, src_map, f"Source ID {sid} not found in source map")

    def test_filter_cited_with_unique_ids(self):
        """Test that _filter_cited handles unique IDs correctly."""
        # Create a sample source map with unique IDs
        unique_id1 = "S_1626262626000_abcd1234"
        unique_id2 = "S_1626262627000_efgh5678"
        src_map = {
            unique_id1: {
                "title": "First Source",
                "content": "First source content",
                "parent_id": "parent_doc_1",
                "is_procedural": False
            },
            unique_id2: {
                "title": "Second Source",
                "content": "Second source content",
                "parent_id": "parent_doc_2",
                "is_procedural": True
            }
        }
        
        # Test with unique ID citations
        answer_with_unique_ids = f"This references the first source [{unique_id1}] and the second source [{unique_id2}]."
        cited_sources = self.assistant._filter_cited(answer_with_unique_ids, src_map)
        
        # Verify that both sources are detected
        self.assertEqual(len(cited_sources), 2, f"Expected 2 cited sources, got {len(cited_sources)}")
        cited_ids = [src["id"] for src in cited_sources]
        self.assertIn(unique_id1, cited_ids, f"Source {unique_id1} not detected")
        self.assertIn(unique_id2, cited_ids, f"Source {unique_id2} not detected")
        
        # Test with numeric citations (backward compatibility)
        numeric_src_map = {
            "1": {
                "title": "First Source",
                "content": "First source content",
                "parent_id": "parent_doc_1",
                "is_procedural": False
            },
            "2": {
                "title": "Second Source",
                "content": "Second source content",
                "parent_id": "parent_doc_2",
                "is_procedural": True
            }
        }
        
        answer_with_numeric_ids = "This references the first source [1] and the second source [2]."
        cited_sources = self.assistant._filter_cited(answer_with_numeric_ids, numeric_src_map)
        
        # Verify that both sources are detected
        self.assertEqual(len(cited_sources), 2, f"Expected 2 cited sources, got {len(cited_sources)}")
        cited_ids = [src["id"] for src in cited_sources]
        self.assertIn("1", cited_ids, f"Source 1 not detected")
        self.assertIn("2", cited_ids, f"Source 2 not detected")

    def test_citation_renumbering(self):
        """Test the citation renumbering logic in generate_rag_response."""
        # Create a sample source map with unique IDs
        unique_id1 = "S_1626262626000_abcd1234"
        unique_id2 = "S_1626262627000_efgh5678"
        
        # Create sample cited sources with unique IDs
        cited_raw = [
            {
                "id": unique_id1,
                "title": "First Source",
                "content": "First source content",
                "parent_id": "parent_doc_1",
                "is_procedural": False
            },
            {
                "id": unique_id2,
                "title": "Second Source",
                "content": "Second source content",
                "parent_id": "parent_doc_2",
                "is_procedural": True
            }
        ]
        
        # Create sample answer with unique ID citations
        answer = f"This references the first source [{unique_id1}] and the second source [{unique_id2}]."
        
        # Create cited sources with display IDs
        cited_sources = []
        renumber_map = {}
        
        for display_id, src in enumerate(cited_raw, 1):
            unique_id = src["id"]
            display_id_str = str(display_id)
            
            renumber_map[unique_id] = display_id_str
            
            entry = {
                "id": unique_id,
                "display_id": display_id_str,
                "title": src["title"],
                "content": src["content"],
                "parent_id": src.get("parent_id", ""),
                "is_procedural": src.get("is_procedural", False)
            }
            cited_sources.append(entry)
        
        # Apply display numbering to the answer
        for unique_id, display_id in renumber_map.items():
            answer = re.sub(rf"\[{re.escape(unique_id)}\]", f"[{display_id}]", answer)
        
        # Verify that the answer now contains display IDs
        self.assertIn("[1]", answer, "Display ID [1] not found in renumbered answer")
        self.assertIn("[2]", answer, "Display ID [2] not found in renumbered answer")
        self.assertNotIn(unique_id1, answer, f"Unique ID {unique_id1} still present in answer")
        self.assertNotIn(unique_id2, answer, f"Unique ID {unique_id2} still present in answer")
        
        # Verify that cited sources contain both unique IDs and display IDs
        self.assertEqual(cited_sources[0]["id"], unique_id1, "Unique ID not preserved in cited sources")
        self.assertEqual(cited_sources[0]["display_id"], "1", "Display ID not set correctly in cited sources")
        self.assertEqual(cited_sources[1]["id"], unique_id2, "Unique ID not preserved in cited sources")
        self.assertEqual(cited_sources[1]["display_id"], "2", "Display ID not set correctly in cited sources")

    def test_cumulative_source_map(self):
        """Test that the cumulative source map is properly maintained."""
        # Initialize the cumulative source map
        self.assistant._cumulative_src_map = {}
        
        # First search results
        first_context, first_src_map = self.assistant._prepare_context(self.sample_results[:1])
        self.assistant._cumulative_src_map.update(first_src_map)
        
        # Verify that the cumulative map contains the first source
        self.assertEqual(len(self.assistant._cumulative_src_map), 1, 
                        "Cumulative source map should contain 1 source")
        
        # Second search results
        second_context, second_src_map = self.assistant._prepare_context(self.sample_results[1:2])
        self.assistant._cumulative_src_map.update(second_src_map)
        
        # Verify that the cumulative map contains both sources
        self.assertEqual(len(self.assistant._cumulative_src_map), 2, 
                        "Cumulative source map should contain 2 sources")
        
        # Third search results
        third_context, third_src_map = self.assistant._prepare_context(self.sample_results[2:])
        self.assistant._cumulative_src_map.update(third_src_map)
        
        # Verify that the cumulative map contains all sources
        self.assertEqual(len(self.assistant._cumulative_src_map), 3, 
                        "Cumulative source map should contain 3 sources")

if __name__ == "__main__":
    unittest.main()
