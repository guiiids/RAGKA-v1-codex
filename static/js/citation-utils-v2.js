/**
 * Citation Utilities V2 - Redis-Based Message-Scoped Citations
 * 
 * Clean, simple approach:
 * - Each message has its own citation array [1], [2], [3]
 * - No complex ID mapping
 * - Direct message-scoped source linking
 * - Redis-backed storage for persistence
 */

(function() {
  'use strict';

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
   * Generate unique message ID based on content and timestamp
   * @param {string} query - The user query
   * @returns {string} - Unique message ID
   */
  function generateMessageId(query = '') {
    const timestamp = Date.now();
    const content = query.substring(0, 50); // First 50 chars
    const hash = btoa(content + timestamp).replace(/[^a-zA-Z0-9]/g, '').substring(0, 8);
    return `msg_${hash}`;
  }

  /**
   * Store citations for a message in Redis via API
   * @param {string} sessionId - Session identifier
   * @param {string} messageId - Message identifier
   * @param {Array} sources - Array of source objects
   * @returns {Promise<boolean>} - Success status
   */
  async function storeCitations(sessionId, messageId, sources) {
    try {
      const response = await fetch('/api/citations/store', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_id: sessionId,
          message_id: messageId,
          sources: sources
        })
      });
      
      const result = await response.json();
      return result.success || false;
    } catch (error) {
      console.warn('Failed to store citations:', error);
      return false;
    }
  }

  /**
   * Retrieve citations for a message from Redis via API
   * @param {string} sessionId - Session identifier
   * @param {string} messageId - Message identifier
   * @returns {Promise<Array>} - Array of citation objects
   */
  async function getCitations(sessionId, messageId) {
    try {
      const response = await fetch(`/api/citations/get?session_id=${sessionId}&message_id=${messageId}`);
      const result = await response.json();
      return result.citations || [];
    } catch (error) {
      console.warn('Failed to get citations:', error);
      return [];
    }
  }

  /**
   * Format message with simple, message-scoped citations
   * @param {string} text - Raw message text with citations
   * @param {Array} sources - Array of source objects
   * @param {string} sessionId - Session identifier
   * @param {string} query - Original query for message ID generation
   * @returns {Object} - {formattedText, messageId}
   */
  function formatMessage(text, sources = [], sessionId = 'default', query = '') {
    if (typeof text !== 'string') {
      console.warn('formatMessage: Expected string, got:', typeof text);
      return { formattedText: String(text || ''), messageId: null };
    }
    // If the message includes citation-link HTML, skip markdown escaping/rendering, just return as trusted HTML
    if (text.includes('class="citation-link"')) {
      return { formattedText: text, messageId: null };
    }

    try {
      // Generate consistent message ID
      const messageId = generateMessageId(query);
      
      // Store citations in Redis if sources provided
      if (sources && sources.length > 0) {
        storeCitations(sessionId, messageId, sources);
      }

      // Create mapping from markers to source objects
      const sourceMap = new Map();
      sources.forEach(src => {
        if (src.display_id !== undefined) {
          sourceMap.set(String(src.display_id), src);
        }
        if (src.id) {
          sourceMap.set(String(src.id), src);
        }
      });

      let processedText = text.replace(
        /\[([^\]]+)\]/g,
        function(match, citationContent) {
          let sourceObj = null;

          // Direct numeric match on display_id
          if (/^\d+$/.test(citationContent)) {
            sourceObj = sources.find(s => String(s.display_id) === citationContent);
          }

          // Lookup in source map
          if (!sourceObj && sourceMap.has(citationContent)) {
            sourceObj = sourceMap.get(citationContent);
          }

          if (sourceObj && sourceObj.id) {
            return `<sup><a href="#source-${sourceObj.id}" class="citation-link text-blue-600 hover:text-blue-800" data-source-id="${sourceObj.id}">[${sourceObj.display_id}]</a></sup>`;
          }

          return match;
        }
      );

      // Apply markdown formatting if marked.js is available
      if (typeof marked !== 'undefined') {
        processedText = marked.parse(processedText, {
          gfm: true,
          breaks: true,
          sanitize: false
        });
      } else {
        // Basic formatting fallback
        processedText = processedText
          .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
          .replace(/\*(.*?)\*/g, '<em>$1</em>')
          .replace(/\n/g, '<br>');
      }

      return { formattedText: processedText, messageId: messageId };
      
    } catch (error) {
      console.error('Error in formatMessage:', error);
      return { 
        formattedText: escapeHtml(text).replace(/\n/g, '<br>'), 
        messageId: generateMessageId(query) 
      };
    }
  }

  /**
   * Generate HTML for Sources section with message-scoped IDs
   * @param {Array} sources - Array of source objects
   * @param {string} messageId - Message identifier
   * @returns {string} - HTML string for sources section
   */
  function addSourcesUtilizedSection(sources) {
    if (!sources || !Array.isArray(sources) || sources.length === 0) {
      return '';
    }

    let sourcesHtml = `<div class="sources-section mt-4"><strong>Sources:</strong><div class="sources-container mt-2">`;

    sources.forEach(source => {
      const displayNum = source.display_id || '';
      const sourceId = `source-${source.id || displayNum}`;
      
      // Extract source information
      let title = '';
      let content = '';
      
      if (typeof source === 'string') {
        title = source.length > 100 ? source.substring(0, 100) + '...' : source;
        content = source;
      } else if (typeof source === 'object' && source !== null) {
        title = source.title || source.id || `Source ${displayNum}`;
        content = source.content || '';
      } else {
        title = `Source ${displayNum}`;
        content = String(source || '');
      }

      // Escape content for security
      title = escapeHtml(title);
      content = escapeHtml(content);

      // Determine if content needs truncation
      const isLongContent = content.length > 200;
      const truncatedContent = isLongContent ? 
        content.substring(0, 200) + '...' : 
        content;

      // Build source HTML with unique source ID
      sourcesHtml += `
        <div id="${sourceId}" class="source-item mb-3 p-3 bg-gray-50 rounded border-l-4 border-blue-200" data-source-id="${source.id || displayNum}">
          <div class="source-header mb-2">
            <strong class="text-blue-700">[${displayNum}]</strong>
            <strong class="text-gray-800">${title}</strong>
          </div>
          <div class="source-content text-gray-600 text-sm">
            <div class="source-preview">${truncatedContent}</div>
            ${isLongContent ?
              `<div class="source-full hidden">${content}</div>
               <button class="toggle-source-btn text-blue-600 text-xs mt-2 hover:underline focus:outline-none" data-source-id="${source.id || displayNum}">Show more</button>`
              : ''}
          </div>
        </div>
      `;
    });

    sourcesHtml += '</div></div>';
    return sourcesHtml;
  }

  /**
   * Handle citation link clicks - scroll to message-scoped source
   * @param {Event} e - Click event
   */
  function handleCitationClick(e) {
    e.preventDefault();
    e.stopPropagation();

    const link = e.target.closest('.citation-link');
    if (!link) return;

    const sourceId = link.getAttribute('data-source-id');
    const targetId = `source-${sourceId}`;

    console.log(`Citation clicked: ${sourceId}`);

    // Find and scroll to the target source
    const targetElement = document.getElementById(targetId);
    if (targetElement) {
      targetElement.scrollIntoView({ behavior: 'smooth', block: 'center' });

      // Highlight the target temporarily
      targetElement.classList.add('bg-yellow-200', 'border-yellow-400');
      setTimeout(() => {
        targetElement.classList.remove('bg-yellow-200', 'border-yellow-400');
      }, 2000);
    } else {
      console.warn(`Source element not found: ${targetId}`);
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
    const sourceId = btn.getAttribute('data-source-id');
    const sourceItem = document.getElementById(`source-${sourceId}`);
    if (!sourceItem) return;

    const preview = sourceItem.querySelector('.source-preview');
    const full = sourceItem.querySelector('.source-full');

    if (!preview || !full) return;

    if (full.classList.contains('hidden')) {
      // Show full content
      preview.classList.add('hidden');
      full.classList.remove('hidden');
      btn.textContent = 'Show less';
    } else {
      // Show preview
      preview.classList.remove('hidden');
      full.classList.add('hidden');
      btn.textContent = 'Show more';
    }
  }

  /**
   * Attach event handlers for citation links and source toggles
   * This function is idempotent - can be called multiple times safely
   */
  function attachCitationHandlers() {
    // Remove existing handlers to prevent duplicates
    document.querySelectorAll('.citation-link').forEach(link => {
      link.removeEventListener('click', handleCitationClick);
      link.addEventListener('click', handleCitationClick);
    });
    
    document.querySelectorAll('.toggle-source-btn').forEach(btn => {
      btn.removeEventListener('click', handleSourceToggle);
      btn.addEventListener('click', handleSourceToggle);
    });
  }

  /**
   * Initialize citation system with DOM observation
   */
  function initializeCitationSystem() {
    // Attach handlers initially
    attachCitationHandlers();
    
    // Re-attach handlers when new content is added
    const observer = new MutationObserver(function(mutations) {
      let shouldReattach = false;
      mutations.forEach(function(mutation) {
        if (mutation.type === 'childList') {
          mutation.addedNodes.forEach(function(node) {
            if (node.nodeType === Node.ELEMENT_NODE) {
              if (node.querySelector && (
                node.querySelector('.citation-link') || 
                node.querySelector('.toggle-source-btn') ||
                node.classList.contains('citation-link') ||
                node.classList.contains('toggle-source-btn')
              )) {
                shouldReattach = true;
              }
            }
          });
        }
      });
      
      if (shouldReattach) {
        setTimeout(attachCitationHandlers, 100);
      }
    });

    // Observe document for changes
    observer.observe(document.body, {
      childList: true,
      subtree: true
    });
  }

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeCitationSystem);
  } else {
    initializeCitationSystem();
  }

  // Export functions to window for global access
  window.CitationUtils = {
    escapeHtml: escapeHtml,
    formatMessage: formatMessage,
    addSourcesUtilizedSection: addSourcesUtilizedSection,
    generateMessageId: generateMessageId,
    storeCitations: storeCitations,
    getCitations: getCitations,
    attachCitationHandlers: attachCitationHandlers
  };

  // Backward compatibility
  window.escapeHtml = escapeHtml;
  window.formatMessage = function(text, sources, messageId) {
    const sessionId = window.sessionId || 'default';
    const query = text ? text.substring(0, 50) : '';
    const result = formatMessage(text, sources, sessionId, query);
    return result.formattedText;
  };
  window.addSourcesUtilizedSection = addSourcesUtilizedSection;
  window.attachCitationHandlers = attachCitationHandlers;

  console.log('Citation Utilities V2 loaded successfully');

})();
