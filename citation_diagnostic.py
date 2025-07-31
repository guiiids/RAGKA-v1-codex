import logging
import os
from rag_assistant_v2 import FlaskRAGAssistantV2, get_phase_logger

# Setup detailed logging to capture the new debug output
log_level_str = os.environ.get("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_str, logging.INFO)

# Get the logger and set its level
logger = get_phase_logger(3)
logger.setLevel(log_level)

# Also, ensure the handlers have the correct level
for handler in logging.getLogger('rag_improvement').handlers:
    handler.setLevel(log_level)

logger.info("--- Starting Citation Diagnostic ---")

def run_diagnostic():
    """
    Runs a diagnostic test to debug the citation repetition issue.
    """
    try:
        # 1. Instantiate the RAG assistant
        # We can pass an empty settings dict as we will manually set up the state.
        assistant = FlaskRAGAssistantV2(settings={})
        logger.info("RAG Assistant instantiated.")

        # 2. Define a query that triggers the issue
        query = "What is the difference between CrossLab Connect and iLab?"
        logger.info(f"Test Query: {query}")

        # 3. Simulate the internal state that leads to the problem.
        # This involves manually setting the _cumulative_src_map and other
        # relevant attributes to mimic a multi-turn conversation.

        # Simulate sources from a previous turn (some with same title)
        assistant._cumulative_src_map = {
            'S_1721728802738_d8e8f33f': {'title': 'iLab Community_2312958.pdf', 'content': 'Content about iLab Community.', 'parent_id': 'doc1', 'is_procedural': False},
            'S_1721728802739_a1b2c3d4': {'title': 'Key iLab Terms_261285.pdf', 'content': 'Content with key iLab terms.', 'parent_id': 'doc2', 'is_procedural': False},
            'S_1721728802740_e5f6g7h8': {'title': 'Key iLab Terms_261285.pdf', 'content': 'More content with key iLab terms.', 'parent_id': 'doc2', 'is_procedural': False},
            'S_1721728802741_i9j0k1l2': {'title': 'iLab Registration & Login Guide_2287669.pdf', 'content': 'Guide to iLab registration.', 'parent_id': 'doc3', 'is_procedural': False},
            'S_1721728802742_m3n4o5p6': {'title': 'iLab Quick-Start Guide_1475196.pdf', 'content': 'Quick start guide for iLab.', 'parent_id': 'doc4', 'is_procedural': False}
        }
        
        # Simulate the _display_ordered_citations from a previous turn
        assistant._display_ordered_citations = list(assistant._cumulative_src_map.keys())
        assistant._display_ordered_citation_map = assistant._cumulative_src_map
        
        logger.info(f"Simulated cumulative source map with {len(assistant._cumulative_src_map)} sources.")

        # 4. Simulate the model's response that contains repeated citation numbers
        simulated_answer = """
        No, CrossLab Connect (CLC) is not the same as iLab. While both are Agilent platforms, they serve different purposes and cater to distinct workflows.

        CrossLab Connect:
        Purpose: Focuses on streamlining laboratory operations, asset management, service requests, and data monitoring. It integrates tools like MyAgilent for unified access to Agilent services [1], [4], [5].
        Features:
        Provides graphical insights on dashboards for tracking support requests and assets [4], [5].
        Offers enhanced onboarding and authentication processes, including CRM Contact ID and SSO security [4].
        Includes tools like Smart Alerts for secure data connections and monitoring [4].
        Supports service submissions with features like direct photo capture [5].
        Applications: Ideal for labs looking to optimize workflows, manage assets, and improve data security [4], [5].
        
        iLab:
        Purpose: Designed for managing core facilities, labs, and workflows, with tools for ordering services, managing funds, and generating reports [4], [4].
        Features:
        Provides roles like Institutional Administrators, Principal Investigators, and Core Administrators for managing lab memberships and financial approvals [4], [4].
        Offers resources like forums, blogs, how-to videos, and a resource library for user support [1].
        Hosted on regional servers for optimized performance and compliance with local regulations [4].
        Applications: Primarily used for research and administrative workflows in labs and institutions [4], [4].
        
        Key Differences:
        Focus: CrossLab Connect emphasizes asset management and service requests, while iLab focuses on workflow and financial management for labs and core facilities.
        Integration: CrossLab Connect integrates with MyAgilent for unified access, whereas iLab is hosted on regional servers tailored to institutional needs.
        User Base: iLab is used globally by institutions and labs, while CrossLab Connect is more focused on operational and service management.
        
        In summary, CrossLab Connect and iLab are distinct platforms tailored to different aspects of laboratory management and operations [1], [4], [4], [5].
        """
        logger.info("Using simulated answer for diagnosis.")

        # 5. Call the function under investigation directly
        logger.info("Calling _assemble_cited_sources to trigger the new logging...")
        cited_sources, renumber_map = assistant._assemble_cited_sources(simulated_answer, assistant._cumulative_src_map)

        # 6. Print the results for analysis
        print("\n--- DIAGNOSTIC RESULTS ---")
        print(f"Number of cited sources returned: {len(cited_sources)}")
        
        print("\nCited Sources (with Display IDs):")
        for source in cited_sources:
            print(f"  Display ID: {source.get('display_id')}, Title: {source.get('title')}, Unique ID: {source.get('id')}")

        print("\nRenumber Map:")
        for unique_id, display_id in renumber_map.items():
            print(f"  Unique ID: {unique_id} -> Display ID: {display_id}")
            
        print("\n--- END OF DIAGNOSTIC RESULTS ---\n")
        logger.info("--- Citation Diagnostic Finished ---")

    except Exception as e:
        logger.error(f"An error occurred during the diagnostic: {e}", exc_info=True)

if __name__ == "__main__":
    # Set environment variable to see detailed logs
    # Example: LOG_LEVEL=DEBUG python citation_diagnostic.py
    run_diagnostic()
