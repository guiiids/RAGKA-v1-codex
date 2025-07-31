## __Critical Analysis & Risk Assessment__

After reviewing the code deeply, here are the __key risks__ that could break the implementation:

1. __Script loading race condition__: Other scripts trying to use citation functions before citation-utils.js loads
2. __Message ID inconsistency__: Different modes generate different messageId formats, breaking source lookups
3. __Event handler conflicts__: Multiple scripts attaching click handlers to same elements
4. __Source data format variations__: Backend sends sources in different shapes (string vs object vs mixed)
5. __Toggle mode integration__: Dynamic/classic toggle must seamlessly work with new utility
6. __Existing chat history__: Old messages with citations must still work after migration

## __Bulletproof Implementation Plan__

### __Phase 1: Create Robust Citation-Utils.js (1 file)__

__Key Design Decisions:__

- __Defensive programming__: Handle all source format variations gracefully
- __Idempotent handlers__: Can be called multiple times without duplicating event listeners
- __Backward compatibility__: Support existing citation formats and data structures
- __Error recovery__: Graceful degradation when sources are missing/malformed

### __Phase 2: Strategic Refactoring (Touch only 3 specific files)__

__Files to modify:__

1. `static/js/citation-utils.js` (create)
2. Template that loads scripts (add script tag)
3. `static/js/dev_eval_chat.js` (remove ChatHelpers.formatMessage, ChatHelpers.escapeHtml)

__Files to leave UNTOUCHED:__

- `citation-toggle.js` (already uses window.formatMessage if available)
- `unifiedEval.js` (already uses window.formatMessage if available)
- All Python/backend code
- Templates (except for script loading)

### __Phase 3: Integration Strategy__

__Critical Implementation Details:__

- Citation-utils.js will detect and handle both `[1]` and `[S_xxxxx]` formats
- Will maintain `window.messageSourcesMap` for message-specific sources
- Will update `window.lastSources` for backward compatibility
- Will use existing CSS classes and DOM structure

### __Phase 4: Minimal Essential Testing__

__4 Real-Data Test Scenarios__ (you test these):

1. __Basic Chat__: Ask a question, verify citations [1], [2] render and click correctly
2. __Dev Eval Mode__: Run dev evaluation, verify sources display and expand/collapse works
3. __Citation Toggle__: Switch between dynamic/classic modes, verify both work
4. __Mixed Source Types__: Test with both string and object sources

## __Detailed Implementation Steps__

### __Step 1: Create `static/js/citation-utils.js`__

This will be a __single, comprehensive file__ that handles:

- HTML escaping (robust, XSS-safe)
- Citation parsing (both [n] and [S_xxxxx] formats)
- Source rendering with expand/collapse
- Click handler attachment (idempotent)
- Integration with existing toggle system

### __Step 2: Update Script Loading__

Find your main template (likely `templates/index.html` or inline in `main.py`) and add:

```html
<script src="/static/js/citation-utils.js"></script>
```

__Before__ other citation-using scripts.

### __Step 3: Remove Duplicate Logic__

In `dev_eval_chat.js`, remove the `ChatHelpers.escapeHtml` and `ChatHelpers.formatMessage` functions, replace with direct calls to `window.escapeHtml` and `window.formatMessage`.

### __Step 4: Verify Integration__

The existing code in `citation-toggle.js` and `unifiedEval.js` already checks for `window.formatMessage` - they'll automatically use the new utility.

## __Success Criteria__

After implementation:

- All citation rendering goes through __one file only__
- No duplicate logic anywhere
- All existing functionality works unchanged
- Future citation fixes require editing __only citation-utils.js__

## __Test Plan (You Execute)__

__Test 1__: Basic functionality

- Start the app, ask any question that returns sources
- Verify citations [1], [2] appear as clickable links
- Click a citation, verify it scrolls to the correct source

__Test 2__: Dev evaluation

- Enter dev evaluation mode, run a query
- Verify sources display with "Show more" buttons
- Test expand/collapse functionality

__Test 3__: Citation toggle

- Toggle between dynamic and classic citation modes
- Verify citations work in both modes

__Test 4__: Edge cases

- Test with mixed source formats (if your backend sends different types)

## __Documentation File__

At the end, I'll create `CITATION_SYSTEM.md` explaining:

- How the modular system works
- Where to make changes for citation enhancements
- Integration points with existing code
- Troubleshooting guide

---

__This approach minimizes risk by:__

- Touching only essential files
- Leveraging existing integration points
- Using defensive programming patterns
- Providing clear rollback plan (just remove the script tag)

Ready to proceed? This will be a clean, single-attempt success.
