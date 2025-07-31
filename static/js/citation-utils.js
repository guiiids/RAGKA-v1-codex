/**
 * Citation Utilities Module
 * Single source of truth for all citation rendering, escaping, and linking logic
 * 
 * CRITICAL: All citation rendering logic in this project MUST be implemented ONLY in this file.
 * Any fixes or enhancements to citation links, markdown patterns, or hyperlinking must be made here and nowhere else.
 */

(function() {
  'use strict';

  // Global message sources map for message-specific source tracking
  if (!window.messageSourcesMap) {
    window.messageSourcesMap = {};
  }

  /**
   * Robust HTML escaping to prevent XSS attacks
   * @param {string} unsafe - The unsafe string to escape
   * @returns {string} - HTML-escaped string
   */
  function escapeHtml(unsafe) {
    if (typeof unsafe !== 'string') {
      console.warn('escapeHtml: Expected string, got:', typeof unsafe);
      return String(unsafe || '');
    }
    
    const div = document.createElement('div');
    div.textContent = unsafe;
    return div.innerHTML;
  }

  /**
   * Format message with citation links, markdown, and other formatting
   * @param {string} text - Raw message text with citations
   * @param {Array} sources - Array of source objects or strings
   * @param {string} messageId - Unique message identifier
   * @returns {string} - Formatted HTML string
   */
  function formatMessage(text, sources = null, messageId = null) {
    if (typeof text !== 'string') {
      console.warn('formatMessage: Expected string, got:', typeof text);
      return String(text || '');
    }

    try {
      // Generate unique message ID if not provided
      const msgId = messageId || `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      
      // Use provided sources or fallback to window.lastSources
      const sourcesToUse = sources || window.lastSources || [];
      
      // Store sources for this message
      if (sourcesToUse.length > 0) {
        window.messageSourcesMap[msgId] = [...sourcesToUse];
        // Update lastSources for backward compatibility
        window.lastSources = [...sourcesToUse];
      }

      // Build mapping objects for citation resolution
      let id2display = {}, display2id = {};
      sourcesToUse.forEach((src, index) => {
        if (typeof src === 'object' && src !== null) {
          if (src.id) id2display[src.id] = src.display_id || (index + 1).toString();
          if (src.display_id) display2id[src.display_id] = src.id;
        }
      });

      // Process citations in the text
      let processedText = text.replace(
        /\[([^\]]+)\]/g,
        function(match, citationContent) {
          // Handle numeric citations [1], [2], etc.
          if (/^\d+$/.test(citationContent)) {
            const displayId = citationContent;
            let uniqueId = displayId; // fallback
            
            // Find the source with this display_id to get its unique ID
            if (display2id[displayId]) {
              uniqueId = display2id[displayId];
            }

            return `<sup class="text-2xl"><a href="#source-${uniqueId}" class="citation-link text-xs text-blue-600" data-source-id="${uniqueId}" data-message-id="${msgId}">[${displayId}]</a></sup>`;
          }
          
          // Handle internal source IDs [S_xxxxx]
          if (citationContent.startsWith('S_')) {
            const sourceId = citationContent;
            let displayId = '1'; // fallback
            
            // Find the source with this ID to get its display_id
            const sourceIndex = sourcesToUse.findIndex(s => s && s.id === sourceId);
            if (sourceIndex !== -1) {
              const source = sourcesToUse[sourceIndex];
              displayId = (source && source.display_id) ? source.display_id : (sourceIndex + 1).toString();
            }

            return `<sup class="text-2xl"><a href="#source-${sourceId}" class="citation-link text-xs text-blue-600" data-source-id="${sourceId}" data-message-id="${msgId}">[${displayId}]</a></sup>`;
          }
          
          // For any other format, return as-is
          return match;
        }
      );

      // Try to use marked.js for markdown rendering if available
      if (typeof marked !== 'undefined') {
        return marked.parse(processedText, {
          gfm: true,
          breaks: true,
          sanitize: false,
          smartLists: true,
          smartypants: true
        });
      } else {
        // Fallback to basic formatting
        return processedText
          .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
          .replace(/\*(.*?)\*/g, '<em>$1</em>')
          .replace(/\n/g, '<br>');
      }
    } catch (error) {
      console.error('Error in formatMessage:', error);
      // Graceful degradation - return escaped text with basic formatting
      return escapeHtml(text).replace(/\n/g, '<br>');
    }
  }

  /**
   * Generate HTML for Sources Utilized section
   * @param {Array} sources - Array of source objects or strings
   * @param {string} messageId - Message ID for source association
   * @returns {string} - HTML string for sources section
   */
  function addSourcesUtilizedSection(sources, messageId) {
    if (!sources || !Array.isArray(sources) || sources.length === 0) {
      return '';
    }

    const msgId = messageId || `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    
    // Store sources for this message
    window.messageSourcesMap[msgId] = [...sources];

    let sourcesHtml = `<strong>Sources:</strong><br><div class="sources-container" data-message-id="${msgId}">`;
    
    sources.forEach((source, index) => {
      // Determine source ID and display ID
      let sourceId, displayId;
      
      if (typeof source === 'object' && source !== null) {
        sourceId = source.id || `source-${index + 1}`;
        displayId = source.display_id || (index + 1).toString();
      } else {
        sourceId = `source-${index + 1}`;
        displayId = (index + 1).toString();
      }

      // Start source item with unique id for citation links
      sourcesHtml += `<div id="source-${sourceId}" class="source-item mb-2 p-2 bg-gray-50 rounded">`;
      
      // Extract title and content
      let sourceTitle = '';
      let sourceContent = '';

      if (typeof source === 'string') {
        if (source.length > 100) {
          sourceTitle = source.substring(0, 100) + '...';
          sourceContent = source;
        } else {
          sourceTitle = source;
          sourceContent = '';
        }
      } else if (typeof source === 'object' && source !== null) {
        sourceTitle = source.title || source.id || `Source ${displayId}`;
        sourceContent = source.content || '';
      }

      // Escape content for security
      sourceTitle = escapeHtml(sourceTitle);
      sourceContent = escapeHtml(sourceContent);

      // Determine if content needs truncation
      const isLongContent = sourceContent.length > 150;
      const truncatedContent = isLongContent ? 
        sourceContent.substring(0, 150) + '...' : 
        sourceContent;

      // Build source HTML with collapsible content
      sourcesHtml += `
        <div>
          <strong>[${displayId}]</strong> <strong>${sourceTitle}</strong>
          <div class="source-content">${truncatedContent}</div>
          ${isLongContent ? 
            `<div class="source-full-content hidden">${sourceContent}</div>
             <button class="toggle-source-btn text-blue-600 text-xs mt-1 hover:underline">Show more</button>` 
            : ''}
        </div>
      `;

      sourcesHtml += '</div>';
    });

    sourcesHtml += '</div>';
    return sourcesHtml;
  }

  /**
   * Attach event handlers for citation links and source toggles
   * This function is idempotent - can be called multiple times safely
   */
  function attachCitationLinkHandlers() {
    // Remove existing handlers to prevent duplicates
    document.querySelectorAll('.citation-link').forEach(link => {
      link.removeEventListener('click', handleCitationClick);
    });
    
    document.querySelectorAll('.toggle-source-btn').forEach(btn => {
      btn.removeEventListener('click', handleSourceToggle);
    });

    // Add citation link handlers
    document.querySelectorAll('.citation-link').forEach(link => {
      link.addEventListener('click', handleCitationClick);
    });

    // Add source toggle handlers
    document.querySelectorAll('.toggle-source-btn').forEach(btn => {
      btn.addEventListener('click', handleSourceToggle);
    });
  }

  /**
   * Handle citation link clicks
   * @param {Event} e - Click event
   */
  function handleCitationClick(e) {
    e.preventDefault();
    e.stopPropagation();

    const link = e.target.closest('.citation-link');
    if (!link) return;

    const sourceId = link.getAttribute('data-source-id');
    const messageId = link.getAttribute('data-message-id');
    
    // Log the click if debug logger is available
    if (window.debugLogger) {
      window.debugLogger.log(`Citation link [${sourceId}] clicked`, 'user-action', {
        sourceId: sourceId,
        messageId: messageId
      });
    }

    // Find and scroll to the target source
    const targetElement = document.getElementById(`source-${sourceId}`);
    if (targetElement) {
      targetElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
      
      // Highlight the target temporarily
      targetElement.classList.add('bg-yellow-100');
      setTimeout(() => {
        targetElement.classList.remove('bg-yellow-100');
      }, 2000);
    } else {
      console.warn(`Source element not found for ID: ${sourceId}`);
    }

    // Integration with existing citation toggle system
    if (window.handleCitationClick && typeof window.handleCitationClick === 'function') {
      // Call the existing handler if it exists (for backward compatibility)
      try {
        window.handleCitationClick(e);
      } catch (error) {
        console.warn('Error calling existing handleCitationClick:', error);
      }
    }
  }

  /**
   * Handle source toggle button clicks
   * @param {Event} e - Click event
   */
  function handleSourceToggle(e) {
    e.preventDefault();
    e.stopPropagation();

    const btn = e.target;
    const parentDiv = btn.closest('.source-item');
    if (!parentDiv) return;

    const truncatedEl = parentDiv.querySelector('.source-content');
    const fullEl = parentDiv.querySelector('.source-full-content');

    if (!truncatedEl || !fullEl) return;

    if (truncatedEl.classList.contains('hidden')) {
      // Show truncated, hide full
      truncatedEl.classList.remove('hidden');
      fullEl.classList.add('hidden');
      btn.textContent = 'Show more';
    } else {
      // Show full, hide truncated
      truncatedEl.classList.add('hidden');
      fullEl.classList.remove('hidden');
      btn.textContent = 'Show less';
    }
  }

  // Attach event handlers when DOM is ready or content changes
  function initializeHandlers() {
    attachCitationLinkHandlers();
    
    // Re-attach handlers when new content is added to the DOM
    const observer = new MutationObserver(function(mutations) {
      let shouldReattach = false;
      mutations.forEach(function(mutation) {
        if (mutation.type === 'childList') {
          mutation.addedNodes.forEach(function(node) {
            if (node.nodeType === Node.ELEMENT_NODE) {
              if (node.querySelector && (node.querySelector('.citation-link') || node.querySelector('.toggle-source-btn'))) {
                shouldReattach = true;
              }
            }
          });
        }
      });
      
      if (shouldReattach) {
        setTimeout(attachCitationLinkHandlers, 100);
      }
    });

    // Observe the document for changes
    observer.observe(document.body, {
      childList: true,
      subtree: true
    });
  }

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeHandlers);
  } else {
    initializeHandlers();
  }

  // Export functions to window for global access
  window.citationUtils = {
    escapeHtml: escapeHtml,
    formatMessage: formatMessage,
    addSourcesUtilizedSection: addSourcesUtilizedSection,
    attachCitationLinkHandlers: attachCitationLinkHandlers
  };

  // Direct window access for backward compatibility
  window.escapeHtml = escapeHtml;
  window.formatMessage = formatMessage;
  window.addSourcesUtilizedSection = addSourcesUtilizedSection;
  window.attachCitationLinkHandlers = attachCitationLinkHandlers;

  console.log('Citation utilities loaded successfully');

})();
