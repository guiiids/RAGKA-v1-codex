**To:** [Developer's Name / Dev Team]
**From:** [Your Name]
**Date:** July 16, 2025
**Subject:** Change Request: Implement Unique and Persistent Citation Link IDs in RAG Assistant

-----



### 1\. Overview

This change request addresses a critical bug in the RAG assistant's citation generation logic. Currently, citation links (`<a>` tags) use non-unique IDs, which causes links in previous chat messages to break or point to incorrect sources. The proposed solution will modify the backend processing to ensure every citation link is unique across the entire conversation history, providing a stable and reliable user experience.

### 2\. Current Setup & Issue Analysis

Our current implementation (`script 2`) correctly generates a unique internal ID (e.g., `S1_a1b2c3d4`) for each source when it is first retrieved. The system is designed to be stateful, remembering all sources in a cumulative map.

The issue occurs in the final renumbering stage within the `generate_rag_response` and `stream_rag_response` functions. The logic overwrites the unique internal ID with a simple, sequential display number (`1`, `2`, `3`, etc.) before sending the data to the front end.

**Problem:**
Because the front end receives a non-unique ID (e.g., `id: "1"`), it generates conflicting HTML like `href="#source-1"` in every bot message. As a result, clicking a citation in an older message incorrectly navigates to the source list of the *most recent* message, as it has the same HTML anchor ID.

### 3\. Expected Behavior

  * Citation links (`href` and the anchor `id`) must be unique and persistent throughout a user's entire conversation.
  * The number displayed to the user in brackets (e.g., `[1]`, `[2]`) should still be sequential and reset for each new message for readability.
  * Clicking any citation link, regardless of how old the message is, must navigate to the correct source document information associated with that link.

### 4\. Proposed Solution & Desired Output

The fix requires modifying the backend renumbering logic to preserve the unique ID for linking while creating a separate ID for display.

#### **A. Backend Change (`script 2`)**

In both the `generate_rag_response` and `stream_rag_response` methods, the final processing loop for `cited_raw` must be updated.

**Current Logic to Replace:**

```python
# The original, buggy block
entry = {
    "id": str(new_id), # BUG: Overwrites the unique ID
    "title": src["title"],
    # ...
}
```

**Proposed New Logic:**

```python
# The corrected block
internal_id = src["id"]  # This is the unique ID, e.g., "S1_ab12cd34"
display_id = str(new_id) # This is the simple number to show, e.g., "1"

entry = {
    "id": internal_id, # FIX: Keep the unique internal_id for the link anchor
    "display_id": display_id, # NEW: Add a separate field for the display number
    "title": src["title"],
    "content": src["content"],
    # ... all other necessary fields
}
```

#### **B. Frontend Change**

The front-end code that renders the bot message and sources list must be updated to use this new data structure from the `cited_sources` array.

  * The HTML anchor and link `href` must be constructed using `source.id` (the unique ID).
  * The text displayed to the user inside the `[]` brackets must use `source.display_id`.

**Desired HTML Output Example:**

```html
<p>
  ...some text <a href="#source-S1_a1b2c3d4" data-source-id="S1_a1b2c3d4">[1]</a>.
</p>
...
<div class="sources-section">
  <ol>
    <li>
      <a id="source-S1_a1b2c3d4" href="[some_doc_url]">Document Title.pdf</a>
    </li>
  </ol>
</div>
```

### 5\. Logging Enhancement

To aid in future debugging, please add a log entry immediately after the corrected renumbering loop to confirm that both unique and display IDs are being processed correctly.

**Suggested Log:**

```python
# Add after the 'cited_sources' list is populated
if cited_sources:
    logger.info(
        f"Processed {len(cited_sources)} cited sources. "
        f"Example - Unique ID: {cited_sources[0]['id']}, "
        f"Display ID: {cited_sources[0]['display_id']}"
    )
```

Please review this request and let me know if you have any questions.

Best regards,

[Your Name]