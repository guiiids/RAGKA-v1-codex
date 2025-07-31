"""
RAG consistency test script that runs queries and follow-ups from the UAT document
and displays expected vs. actual responses for human validation
"""
import logging
import json
import os
import re
import time
from rag_assistant_v2 import FlaskRAGAssistant
from rag_improvement_logging import setup_improvement_logging

# Set up logging
logger = setup_improvement_logging()

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Add file handler specifically for consistency test results
consistency_log_file = 'logs/rag_consistency_results.log'
file_handler = logging.FileHandler(consistency_log_file)
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Test cases from the UAT document with expected responses
test_cases = [
    {
        "domain": "Genomics",
        "initial": "A user complains that they get no final libraries on their Magnis instrument despite following the manual precisely. Which questions should I, an Agilent remote engineer, ask to probe how they prepared the samples?",
        "initial_expected": """To troubleshoot why no final libraries are being generated on the Magnis instrument, you should ask the following questions to probe the user's sample preparation process:---### 1. Input DNA/RNA Preparation- How was the input DNA/RNA quantified?- Confirm if the user used a Qubit BR dsDNA assay or Agilent NGS FFPE QC kit to assess DNA quality and concentration [5].- What was the input DNA volume and buffer?- Verify if the DNA was diluted in 1x Low TE buffer to the correct volume (e.g., 50 µL total) [5].- Was enzymatic shearing performed correctly?- If enzymatic shearing was used, ask if the input volume was 14 µL and if the fragmentation time was set appropriately on the touchscreen [4].- Was QC performed after off-deck shearing?- Ensure the user performed quality control on the sheared DNA before loading it onto the Magnis [4].---### 2. Reagent Handling- Were the reagents thawed, vortexed, and spun down?- Confirm if reagents were thawed to room temperature, vortexed horizontally and vertically, and centrifuged to ensure all liquid was at the bottom of the wells [2][3].- Were the reagents free from air bubbles or damage?- Ask if the user visually inspected the reagents for air bubbles or abnormalities before loading them onto the deck [3].- Were the probes dispensed accurately?- Verify if the probes were added to the probe input strip using an appropriate pipette, ensuring precise volumes (e.g., 5 µL or 2 µL for EPIS protocols) [4].---### 3. Deck Setup- Were consumables placed correctly on the deck?- Ask if the user ensured proper placement of tip boxes, HSM plates, and Beads & Buffer plates, ensuring they were latched into the spring-loaded mechanisms [2][3].- Was the Beads & Buffer plate seal inspected?- Confirm if the user checked for warping, bulging, or abnormalities in the Beads & Buffer plate seal [3].- Were tip boxes aligned properly?- Misaligned tip boxes can cause pipetting errors. Ask if the user checked their placement before starting the run [1][2].""",
        "followup": "No sample preparation issues were discovered. What could be the next steps?",
        "followup_expected": """If no sample preparation issues were discovered and an engineer is required to go on-site, the following instructions should be provided to ensure a thorough investigation and resolution:---### 1. Review Site Preparation- Action: Verify that the site meets all preparation requirements, including:- Adequate laboratory space with proper clearances around the instrument.- Correct electrical outlets and power supply.- Environmental conditions (e.g., temperature, humidity) within the specified range [4].- Follow-up: Ensure the instrument is placed in its permanent location and confirm all consumables and supplies are available [4].---### 2. Inspect Instrument Setup- Action: Check the physical setup of the Magnis instrument, including:- Alignment of the Z gantry and pipette module.- Placement of consumables such as tip boxes, reagent plates, and Beads & Buffer plates.- Proper latching of plates into the spring-loaded mechanism [1], [3].- Follow-up: Perform an auto-teach to verify alignment. If auto-teach fails, manually adjust teach points and run post-repair tests [1].---### 3. Check Instrument Components- Action: Inspect critical components for damage or misalignment:- Pipette module barrels for deformation.- Magnets within the HSM for proper positioning [2].- Follow-up: Replace any damaged components and test their functionality.""",
        "initial_required": [
            "investigate why the user is getting no final libraries",
            "### 1. Input DNA/RNA Preparation",
            "### 2. Reagent Handling",
            "### 3. Deck Setup",
        ],
        "followup_required": [
            "If no sample preparation issues were discovered and an engineer is required to go on-site",
            "### 1. Review Site Preparation",
            "### 2. Inspect Instrument Setup",
            "### 3. Check Instrument Components",
        ]
    },
    {
        "domain": "GC",
        "initial": "I am observing high baseline noise and drift in a 7890 GC TCD. Provide me the top 5 causes and possible fixes. Show me documents from both the IKB and from user manuals.",
        "initial_expected": """High baseline noise and drift in a 7890 GC TCD can result from several causes. Based on the provided context, here are the top five causes and their possible fixes:### Causes and Fixes:1. Contaminated Carrier Gas- Cause: Contaminants in carrier gas can saturate traps, leading to high noise levels. This is especially common with nitrogen carrier gas [1].- Fix: Verify the purity of carrier gases. If a new tank was recently installed, test an older tank (if available) to see if noise decreases. Replace or regenerate traps if contamination persists [1].2. Septum Bleed or Inlet Contamination- Cause: Septum bleed from low molecular weight materials or contaminants in the inlet can contribute to baseline noise [1], [3].- Fix: Bakeout the inlet to reduce septum bleed and contaminants. Use high-quality septa stored properly to avoid contamination [1], [3].3. Loose Connections or Signal Path Issues- Cause: Loose connections in the detector or its signal path can generate noise [1].- Fix: Inspect all connections for tightness and verify proper reassembly after recent maintenance [1].4. Environmental Factors (Air Currents)- Cause: Air currents from fans or air conditioners blowing across the GC may interfere with gas exiting the detector, causing fluctuations [1].- Fix: Switch off air current sources near the GC or shield the detector exit to minimize interference [1].5. Detector Contamination- Cause: Gradual contamination of the detector can lead to unacceptable noise levels over time [2], [3].- Fix: Inspect and clean/bake out contaminated detectors as needed (FID, TCD, uECD). Replace parts if necessary following guidance in maintenance manuals like Agilent's 7890 Series Troubleshooting guide [2], [3].""",
        "followup": "Provide detailed instructions for investigating root cause #2.",
        "followup_expected": """### Investigating Root Cause #2: Septum BleedSeptum bleed is a common issue that can contribute to high baseline noise in GC systems. Below are detailed instructions to investigate and address this issue:---### 1. Confirm Symptoms- Observation: High baseline noise or drift, particularly when the inlet temperature is high.- Verification: Lower the inlet temperature temporarily and observe if the noise decreases. If it does, septum bleed is a likely cause [1].---### 2. Inspect the Septum- Action: Check the septum for signs of wear, contamination, or improper installation.- Recommendation: Use only high-quality septa designed for your GC system. Store them in a clean, contamination-free environment [1].---### 3. Perform Bakeout- Purpose: Bakeout helps remove contaminants, including bleed from low molecular weight materials.- Steps:1. Access the bakeout procedure specific to your GC system (e.g., Split/Splitless Inlet Bakeout).2. Follow the instructions in the user manual or maintenance guide to initiate the bakeout process [1], [2].---### 4. Replace the Septum- Action: If the septum is visibly damaged or contaminated, replace it with a new one.- Steps:1. Shut down the GC system and allow it to cool.2. Remove the old septum carefully to avoid introducing contaminants.3. Install the new septum securely, ensuring it is seated properly [1].---### 5. Test the System- Action: After replacing the septum and performing bakeout, restart the GC system.- Verification: Run a test sample to confirm that baseline noise has decreased. Monitor the system for any recurring issues [1].""",
        "initial_required": [
            "High baseline noise and drift",
            "Contaminated Carrier Gas",
            "Septum Bleed",
            "Loose Connections",
            "Environmental Factors",
            "Detector Contamination"
        ],
        "followup_required": [
            "Septum Bleed",
            "Inspect the Septum",
            "Perform Bakeout",
            "Replace the Septum",
            "Test the System"
        ]
    },
    {
        "domain": "LC",
        "initial": "How do I fix a leak between needle and Needle Seat in G1367A Autosampler?",
        "initial_expected": """To fix a leak between the needle and the needle seat in the G1367A Autosampler, follow these steps:1. Inspect for Damage or Blockage: Check if the needle seat is visibly damaged, blocked, or leaking. You can use an eyeglass to inspect for scoring on the needle seat [1].2. Backflush Needle Seat:- Remove the ALS outlet capillary and needle seat capillary.- Connect the needle seat capillary to port 6 of the injection valve or join it with a union to reverse flow direction through the needle seat.- Dial up a flow rate of 0.5–1 ml/min on the pump and open its purge valve.- While purging, lift the needle out using maintenance software (e.g., OpenLab Advisor or ChemStation) to expose it.- Place tissues around to mop up any mobile phase leakage near sensitive areas like leak sensors [1].3. Sonicate Needle Seat:- If backflushing does not resolve the issue, remove and sonicate the needle seat upside down in hot water or 100% B-phase solvent to dissolve any precipitation [1].4. Replace Needle Seat:- If cleaning does not fix leaks, replace both the needle and needle seat as a matching pair to ensure proper sealing [2], [3].- Use tools such as a flathead screwdriver and wrench (p/n 8710-0510). Carefully remove and insert a new high-pressure PEEK-based needle seat (e.g., p/n G1367-87012) into position [4].5. Safety Precautions:- Wear appropriate PPE as described in material safety data sheets provided by chemical vendors.- Be cautious of uncovered needles during handling; use silicon safety tubes supplied with new needles [2], [4].""",
        "followup": "Provide step by step instruction on step #4.",
        "followup_expected": """The provided context does not include specific instructions for replacing the needle-seat in the G1367A autosampler. However, based on my understanding of similar procedures for Agilent autosamplers, here is a general step-by-step guide:1. Preparation:- Ensure all pending or running acquisition jobs are finished.- Stop the flow at the pump and remove solvent lines from eluent bottles to avoid spills.- Close shutoff valves at the pump if available.2. Access Maintenance Mode:- In your user interface or diagnostic software (e.g., Lab Advisor), start maintenance mode and select the "Change Needle/Seat" function.3. Open Autosampler:- Open the front door and remove any side doors or plate trays as needed to access internal components.4. Disconnect Seat Capillary:- Using a 1/4-inch wrench, disconnect the seat capillary from injection valve port 5.5. Remove Old Needle-Seat Assembly:- Use a flat-head screwdriver to carefully ease out and remove the old needle-seat assembly.6. Insert New Needle-Seat Assembly:- Insert the new needle-seat assembly (e.g., part number G1367-87101). Press it firmly into position to ensure proper alignment.7. Reconnect Seat Capillary:- Reconnect the seat capillary to injection valve port 5 using a 1/4-inch wrench.8. Reassemble Components:- Replace any removed components such as plate trays, side doors, etc., ensuring everything is securely reinstalled.9. Exit Maintenance Mode:- Close the "Change Needle/Seat" function in your software and exit maintenance mode.10. Test Functionality:- Run diagnostics or test injections to confirm proper installation and operation of the new needle-seat assembly.""",
        "initial_required": [
            "Inspect for Damage",
            "Backflush Needle Seat",
            "Sonicate Needle Seat",
            "Replace Needle Seat"
        ],
        "followup_required": [
            "Replace Needle-Seat Assembly",
            "Reconnect Seat Capillary",
            "Reassemble Components"
        ]
    },
    {
        "domain": "iLab",
        "initial": "How do I detach an invoice from a billing file in iLab?",
        "initial_expected": """To detach an invoice from a billing file in iLab, follow these steps:### Steps to Detach an Invoice1. Access the Billing Tab:Navigate to the core's Billing Tab to view the list of existing billing events. Ensure the billing event has a status of either "Billing Initialized" or "Draft" [1].2. Locate the Billing Event:Find the billing event that contains the invoice(s) you want to detach [1].3. Open the Invoice:- Click on the appropriate invoice link to display all invoices within the billing event.- Select the magnifying glass icon to the far right of the invoice you wish to detach [1].4. Detach the Invoice:- Once the invoice is open, click the "Detach Invoice" icon at the top of the invoice.- The Detach Invoice window will open. You may enter a note in the provided field, but this is optional.- Click "Detach Invoice" to remove the invoice from the billing event.- A note indicating the invoice has been detached will display at the top of the invoice [1].---### Important Notes- Restrictions:An invoice cannot be detached if:- It has been marked Paid or Partially Paid.- The billing event has a status of "File Sent", meaning all invoices have already been sent to an institutional ERP for final processing [1].- Institutional Settings:Not all institutions allow detached invoices. Institutional administrators determine whether core administrators have the authority to detach invoices from billing events [1].""",
        "followup": "How can I undo this and reattach an invoice?",
        "followup_expected": """To reattach a detached invoice in iLab, follow these steps:### Steps to Reattach a Detached Invoice1. Locate the Detached Invoice:- Navigate to the Billing Tab of the core facility.- Go to the section labeled View Detached Invoices. Detached invoices are identified by their red-lettered "Detached" status [1].2. Select the Invoice:- Use the filter tools within the Invoices filter panel to search for the specific detached invoice, if needed [1].- Click the checkbox next to the invoice you wish to reattach [1].3. Include in a New Billing Event:- Detached invoices are automatically moved into the next billing event created.- Select the checkbox labeled Include at the top of the list to automatically mark all detached invoices as ready for inclusion in the new billing event [1].4. Finalize the Billing Event:- Proceed with the creation or management of the new billing event, ensuring the selected invoice is included [1].---### Important Notes- Detached invoices can only be reattached to new billing events, not to the original event they were removed from [1].- Ensure all necessary corrections or updates to the invoice are made before reattaching it to avoid further issues during processing.""",
        "initial_required": [
            "Access the Billing Tab",
            "Locate the Billing Event",
            "Open the Invoice",
            "Detach the Invoice"
        ],
        "followup_required": [
            "Locate the Detached Invoice",
            "Select the Invoice",
            "Include in a New Billing Event",
            "Finalize the Billing Event"
        ]
    },
    {
        "domain": "OpenLab CDS",
        "initial": "When adding a license to Openlab CDS, what are the most likely causes of \"failed to add license\" errors and how to fix them?",
        "initial_expected": """The most likely causes of "failed to add license" errors when adding a license to OpenLab CDS and their solutions are as follows:### Causes:1. Incorrect Host Name in License File:- The license file contains a server line with a host name that does not match the license server or cannot be resolved by DNS (e.g., "The license file contains a server 'Agilent_OnlineLC_CSC_1' that could not be found by DNS") [3].2. Licensing Support Service Not Running:- The Agilent OpenLab Licensing Support service is stopped or not running in Windows Services, leading to immediate connection refusal when retrying without restarting the service [3].3. Exceeding License File Entry Limit:- The license file contains too many components or entries, exceeding the limit (e.g., 78 entries for OpenLab CDS). This is common with ANY license files that include multiple packages such as third-party drivers and Agilent licenses [2], [5], [5].4. Third-Party Driver Licenses:- The inclusion of unnecessary third-party driver licenses or other features in the license file can cause the failure [2], [5].### Solutions:1. Correct Host Name:- Verify and correct the host name in the license file. If the host name is incorrect, return the license to the customer license pool in Subscribenet and generate a new license file with the correct server name [3].2. Restart Licensing Support Service:- Manually start the Agilent OpenLab Licensing Support service before adding the license. Ensure the service is running properly in Windows Services [3].3. Split License File:- If the license file exceeds the entry limit (e.g., 78 entries), split the file into two parts and add them separately. Remove unnecessary entries such as third-party drivers or redundant features [2], [5], [5].4. Slimmed-Down License File:- Use a modified license file with fewer items. Remove specific entries like third-party drivers (e.g., MassHunter TQ/QTOF and LCMS) and test the modified file to ensure it works [2], [5].5. Generate New License File:- If the existing license file is problematic, generate a new slimmed-down license file (e.g., ANY_NEW.lic) and test it [5].""",
        "followup": "Provide detailed instructions for fixing likely root cause 1 in your answer to my question.",
        "followup_expected": """The likely root cause #1 for "failed to add license" errors in OpenLab CDS is incorrect host name in the license file. Below are detailed instructions to fix this issue:### Steps to Fix Incorrect Host Name in the License File:1. Verify the Host Name:- Check the host name specified in the license file. It must match the actual license server's host name.- If the error message indicates that the host name is unknown or cannot be resolved by DNS (e.g., "The license file contains a server 'Agilent_OnlineLC_CSC_1' that could not be found by DNS"), this confirms the issue [2].2. Return the License to the Pool:- Log in to the Subscribenet portal where the license was generated.- Return the problematic license to the customer license pool. This action will make the license available for regeneration [2].3. Generate a New License:- In Subscribenet, create a new license file with the correct host name.- Ensure that the server line in the license file matches the actual license server name configured in your system [2].4. Test the New License:- Add the newly generated license file to OpenLab CDS.- Verify that the system accepts the license without errors.5. Restart Licensing Support Service:- If the issue persists, restart the Agilent OpenLab Licensing Support service in Windows Services to ensure it is running properly [2].""",
        "initial_required": [
            "Incorrect Host Name",
            "Licensing Support Service Not Running",
            "Exceeding License File Entry Limit",
            "Third-Party Driver Licenses"
        ],
        "followup_required": [
            "Verify the Host Name",
            "Return the License to the Pool",
            "Generate a New License",
            "Test the New License"
        ]
    }
]

def run_query_and_log(assistant, test_case, query_type="initial", run_index=0):
    """Run a query and log the response with comparison to expected response"""
    domain = test_case["domain"]
    query = test_case[query_type]
    expected_response = test_case[f"{query_type}_expected"]
    required_phrases = test_case.get(f"{query_type}_required", [])
    
    print(f"\n{'='*80}")
    print(f"DOMAIN: {domain}")
    print(f"QUERY TYPE: {query_type}")
    print(f"RUN: {run_index+1}")
    print(f"{'='*80}")
    print(f"QUERY: {query}")
    print(f"{'='*80}")
    
    try:
        # Generate response
        start_time = time.time()
        # Set is_enhanced to True to bypass the query enhancement which is causing errors
        answer, sources, _, _, context = assistant.generate_rag_response(query, is_enhanced=True)
        end_time = time.time()
        response_time = end_time - start_time
        
        # Log basic information
        logger.info(f"Response received for {domain} {query_type} query (Run {run_index+1})")
        logger.info(f"Response time: {response_time:.2f} seconds")
        logger.info(f"Response length: {len(answer)} characters")
        logger.info(f"Number of sources: {len(sources)}")
        
        # Check for required phrases
        missing_phrases = []
        for phrase in required_phrases:
            if phrase not in answer:
                missing_phrases.append(phrase)
        
        # Print actual response
        print(f"ACTUAL RESPONSE:")
        print(f"{'-'*80}")
        print(answer)
        print(f"{'-'*80}")
        
        # Print expected response (truncated for readability)
        print(f"EXPECTED RESPONSE (first 500 chars):")
        print(f"{'-'*80}")
        print(expected_response[:500] + "..." if len(expected_response) > 500 else expected_response)
        print(f"{'-'*80}")
        
        # Print validation results
        print(f"VALIDATION RESULTS:")
        print(f"{'-'*80}")
        print(f"Response time: {response_time:.2f} seconds")
        print(f"Response length: {len(answer)} characters")
        print(f"Sources cited: {len(sources)}")
        
        if missing_phrases:
            print(f"MISSING REQUIRED PHRASES:")
            for phrase in missing_phrases:
                print(f"  - {phrase}")
            logger.warning(f"Missing required phrases in {domain} {query_type} response (Run {run_index+1}):")
            for phrase in missing_phrases:
                logger.warning(f"  - {phrase}")
        else:
            print(f"All required phrases found ✓")
            logger.info(f"All required phrases found in {domain} {query_type} response (Run {run_index+1})")
        
        # Create a comparison file for detailed human review
        comparison_dir = "comparison_results"
        os.makedirs(comparison_dir, exist_ok=True)
        comparison_file = f"{comparison_dir}/{domain}_{query_type}_run{run_index+1}.txt"
        
        with open(comparison_file, "w") as f:
            f.write(f"DOMAIN: {domain}\n")
            f.write(f"QUERY TYPE: {query_type}\n")
            f.write(f"RUN: {run_index+1}\n")
            f.write(f"{'='*80}\n\n")
            
            f.write(f"QUERY:\n{query}\n\n")
            f.write(f"{'='*80}\n\n")
            
            f.write(f"ACTUAL RESPONSE:\n{answer}\n\n")
            f.write(f"{'='*80}\n\n")
            
            f.write(f"EXPECTED RESPONSE:\n{expected_response}\n\n")
            f.write(f"{'='*80}\n\n")
            
            f.write(f"VALIDATION RESULTS:\n")
            f.write(f"Response time: {response_time:.2f} seconds\n")
            f.write(f"Response length: {len(answer)} characters\n")
            f.write(f"Sources cited: {len(sources)}\n\n")
            
            if missing_phrases:
                f.write(f"MISSING REQUIRED PHRASES:\n")
                for phrase in missing_phrases:
                    f.write(f"  - {phrase}\n")
            else:
                f.write(f"All required phrases found ✓\n")
        
        print(f"\nDetailed comparison saved to: {comparison_file}")
        
        # Log detailed response data
        response_data = {
            "domain": domain,
            "run_index": run_index + 1,
            "query_type": query_type,
            "query": query,
            "response": answer,
            "response_time": response_time,
            "sources_count": len(sources),
            "sources": [{"id": s.get("id"), "title": s.get("title")} for s in sources],
            "missing_phrases": missing_phrases,
            "all_phrases_found": len(missing_phrases) == 0,
            "comparison_file": comparison_file
        }
        
        # Log as JSON for easy parsing
        logger.info(f"RESPONSE_DATA: {json.dumps(response_data)}")
        
        return answer
        
    except Exception as e:
        logger.error(f"Error running {query_type} query for {domain} (Run {run_index+1}): {str(e)}")
        print(f"ERROR: {str(e)}")
        return None

def test_rag_consistency_with_uat_prompts():
    """Run consistency test with UAT prompts"""
    logger.info("Starting RAG consistency test with UAT prompts")
    print("\nRAG CONSISTENCY TEST WITH UAT PROMPTS")
    print("=====================================\n")
    
    # Number of runs per test case
    num_runs = 1  # Starting with 1 run for initial testing
    
    # Create a summary file
    summary_file = "rag_consistency_summary.txt"
    with open(summary_file, "w") as f:
        f.write("RAG CONSISTENCY TEST SUMMARY\n")
        f.write("===========================\n\n")
        f.write(f"Test run at: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    
    # Run each test case
    for test_case in test_cases:
        domain = test_case["domain"]
        logger.info(f"Testing domain: {domain}")
        
        with open(summary_file, "a") as f:
            f.write(f"\nDOMAIN: {domain}\n")
            f.write(f"{'-'*80}\n")
        
        for run in range(num_runs):
            # Create a new assistant instance for each run
            assistant = FlaskRAGAssistant()
            
            # Run initial query
            initial_response = run_query_and_log(
                assistant, 
                test_case, 
                "initial", 
                run
            )
            
            # Run follow-up query if initial query succeeded
            if initial_response:
                followup_response = run_query_and_log(
                    assistant, 
                    test_case, 
                    "followup", 
                    run
                )
            
            logger.info(f"Completed run {run+1} for domain: {domain}")
            
            # Add to summary file
            with open(summary_file, "a") as f:
                f.write(f"Run {run+1}: ")
                if initial_response:
                    f.write("Initial query successful. ")
                    if followup_response:
                        f.write("Follow-up query successful.\n")
                    else:
                        f.write("Follow-up query failed.\n")
                else:
                    f.write("Initial query failed.\n")
    
    logger.info("RAG consistency test with UAT prompts completed")
    print(f"\nTest results logged to: {os.path.abspath(consistency_log_file)}")
    print(f"Summary saved to: {os.path.abspath(summary_file)}")
    print(f"Detailed comparisons saved to: {os.path.abspath('comparison_results')} directory")

if __name__ == "__main__":
    test_rag_consistency_with_uat_prompts()
