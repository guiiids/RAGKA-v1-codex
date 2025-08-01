/**
 * Session-Wide Citation System
 * 
 * Complete rewrite of citation handling using Redis-backed session-wide citation registry.
 * Features:
 * - Persistent citation IDs across the entire session
 * - Deduplication of identical sources
 * - Cross-message citation linking
 * - Robust error handling and fallbacks
 */

(function() {
  'use strict';

  // Session and citation state
  let sessionId = null;
  let citationCache = new Map(); // Local cache for performance
  let debugMode = false;

  /**
   * Initialize the session citation system
   */
  function initializeSessionCitationSystem() {
    // Get session ID from global context or generate one
    sessionId = window.sessionId || generateSessionId();
    window.sessionId = sessionId;
    
    // Enable debug mode if needed
    debugMode = localStorage.getItem('citation-debug') === 'true';
    
    if (debugMode) {
      console.log('🔧 Session Citation System initialized', { sessionId });
    }
    
    // Initialize citation click handlers
    initializeCitationHandlers();
    
    console.log('Session Citation System ready');
  }

  /**
   * Generate a temporary session ID if none exists
   */
  function generateSessionId() {
    return 'temp_' + Math.random().toString(36).substr(2, 9);
  }

  /**
   * Register sources with the session-wide citation registry
   * @param {Array} sources - Array of source objects
   * @returns {Promise<Array>} - Array of sources with assigned IDs
   */
  async function registerSources(sources) {
    if (!sources || !Array.isArray(sources) || sources.length === 0) {
      return [];
    }

    try {
      const response = await fetch('/api/session-citations/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_id: sessionId,
          sources: sources
        })
      });

      const result = await response.json();
      
      if (result.success && result.sources) {
        // Update local cache keyed by unique source.id
        result.sources.forEach(source => {
          if (source.id) {
            citationCache.set(source.id, source);
          }
        });

        if (debugMode) {
          console.log('📚 Registered sources:', result.sources.map(s => ({
            id: s.id,
            title: (s.title || '').substring(0, 30) + '...'
          })));
        }

        return result.sources;
      } else {
        console.warn('Failed to register sources:', result.error);
        return fallbackSources(sources);
      }
      
    } catch (error) {
      console.error('Error registering sources:', error);
      return fallbackSources(sources);
    }
  }

  /**
   * Get source data by unique source ID
   * @param {string|number} sourceId - Source ID to look up
   * @returns {Promise<Object|null>} - Source data or null if not found
   */
  async function getSourceById(sourceId) {
    // Check local cache first
    if (citationCache.has(sourceId)) {
      return citationCache.get(sourceId);
    }

    try {
      const response = await fetch(`/api/session-citations/get?session_id=${sessionId}&source_id=${sourceId}`);
      const result = await response.json();

      if (result.success && result.source) {
        // Cache the result
        citationCache.set(sourceId, result.source);
        return result.source;
      } else {
        if (debugMode) {
          console.warn(`Source not found for ID ${sourceId}:`, result.error);
        }
        return null;
      }

    } catch (error) {
      console.error('Error getting source by ID:', error);
      return null;
    }
  }

  /**
   * Format text with session-wide citations
   * @param {string} text - Raw text with citation markers
   * @param {Array} sources - Array of source objects (will be registered)
   * @returns {Promise<string>} - Formatted HTML with citation links. If the
   *   text already contains pre-rendered citation links, it is returned
   *   unchanged.
   */
  async function formatTextWithCitations(text, sources = []) {
    if (typeof text !== 'string') {
      return String(text || '');
    }

    // If citation links are already present, skip conversion to avoid
    // reprocessing server-rendered citation links
    if (text.includes('session-citation-link')) {
      return text;
    }

    // Register sources first to get session-wide citation IDs
    const registeredSources = await registerSources(sources);
    
    if (debugMode) {
      console.log('🔗 Formatting citations:', {
        originalText: text.substring(0, 100) + '...',
        sourcesCount: sources.length,
        registeredCount: registeredSources.length,
        citationIds: registeredSources.map(s => s.id)
      });
    }
    
    // Map various citation markers to their corresponding source objects
    const messageScope = new Map();
    registeredSources.forEach(source => {
      const displayId = source.display_id || '';
      if (displayId !== '') {
        messageScope.set(String(displayId), source);
      }
      if (source.id) {
        messageScope.set(String(source.id), source);
        // Handle legacy S_ format
        if (source.id.startsWith('S_')) {
          messageScope.set(source.id, source);
        }
      }
    });

    // Process citation markers in the text
    let processedText = text.replace(
      /\[([^\]]+)\]/g,
      function(match, citationContent) {
        let sourceObj = null;

        // Direct numeric match - map using display_id
        if (/^\d+$/.test(citationContent)) {
          sourceObj = registeredSources.find(s => String(s.display_id) === citationContent);
        }

        // Lookup in message scope mapping
        if (!sourceObj && messageScope.has(citationContent)) {
          sourceObj = messageScope.get(citationContent);
        }

        // If we found a valid source, create the link using source.id and display_id
        if (sourceObj && sourceObj.id) {
          return `<sup><a href="#source-${sourceObj.id}" class="session-citation-link text-blue-600 hover:text-blue-800" data-source-id="${sourceObj.id}">[${sourceObj.display_id}]</a></sup>`;
        } else {
          if (debugMode) {
            console.warn('Could not resolve citation:', citationContent);
          }
          // Keep the original if we can't resolve it
          return match;
        }
      }
    );

    // Apply markdown formatting if available
    if (typeof marked !== 'undefined') {
      try {
        processedText = marked.parse(processedText, {
          gfm: true,
          breaks: true,
          sanitize: false
        });
      } catch (error) {
        console.warn('Markdown parsing failed:', error);
        // Basic fallback formatting
        processedText = processedText
          .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
          .replace(/\*(.*?)\*/g, '<em>$1</em>')
          .replace(/\n/g, '<br>');
      }
    } else {
      // Basic formatting fallback
      processedText = processedText
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/\n/g, '<br>');
    }

    if (debugMode) {
      console.log('✅ Citation formatting complete:', {
        processedLength: processedText.length,
        citationLinks: (processedText.match(/session-citation-link/g) || []).length
      });
    }

    return processedText;
  }

  /**
   * Generate sources section HTML
   * @param {Array} sources - Array of registered source objects
   * @returns {string} - HTML string for sources section
   */
  function generateSourcesSection(sources) {
    if (!sources || !Array.isArray(sources) || sources.length === 0) {
      return '';
    }

    let sourcesHtml = `<div class="sources-section mt-4 pt-3 border-t border-gray-200">`;
    sourcesHtml += `<h4 class="text-sm font-semibold text-gray-700 mb-2">Sources Utilized</h4>`;
    sourcesHtml += `<ol class="text-sm text-gray-600 space-y-1 pl-4">`;
    
    sources.forEach(source => {
      const displayId = source.display_id || '';
      const uniqueId = source.id || displayId;
      const title = escapeHtml(source.title || `Source ${displayId}`);

      sourcesHtml += `
        <li>
          <a id="source-${uniqueId}" href="javascript:void(0);"
             class="session-citation-link text-blue-600 hover:underline cursor-pointer"
             data-source-id="${uniqueId}"
             onclick="handleSessionCitationClick('${uniqueId}')">
            [${displayId}] ${title}
          </a>
        </li>`;
    });
    
    sourcesHtml += `</ol></div>`;
    return sourcesHtml;
  }

  /**
   * Handle citation link clicks
   * @param {string|number} sourceId - Source ID that was clicked
   */
  async function handleSessionCitationClick(sourceId) {
    if (debugMode) {
      console.log('🖱️ Citation clicked:', sourceId);
    }

    try {
      const source = await getSourceById(sourceId);

      if (source) {
        showSourceModal(source.display_id || sourceId, source.title || `Source ${source.display_id || sourceId}`, source.content || '');
      } else {
        showSourceModal(sourceId, 'Source Not Available', 'This source could not be retrieved.');
      }

    } catch (error) {
      console.error('Error handling citation click:', error);
      showSourceModal(sourceId, 'Error', 'Failed to retrieve source information.');
    }
  }

  /**
   * Show source content in a modal
   * @param {string|number} displayId - Display ID
   * @param {string} title - Source title
   * @param {string} content - Source content
   */
  function showSourceModal(displayId, title, content) {
    // Remove existing modal if any
    const existingModal = document.getElementById('source-modal');
    if (existingModal) {
      existingModal.remove();
    }

    // Create modal HTML
    const modal = document.createElement('div');
    modal.id = 'source-modal';
    modal.className = 'fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50';
    modal.innerHTML = `
      <div class="bg-white rounded-lg max-w-4xl max-h-[80vh] p-6 m-4 overflow-hidden flex flex-col">
        <div class="flex justify-between items-center mb-4">
          <h3 class="text-lg font-semibold text-gray-900">[${displayId}] ${escapeHtml(title)}</h3>
          <button id="close-modal" class="text-gray-400 hover:text-gray-600 text-xl font-bold">&times;</button>
        </div>
        <div class="flex-1 overflow-y-auto">
          <div class="text-sm text-gray-700 whitespace-pre-wrap">${escapeHtml(content)}</div>
        </div>
      </div>
    `;

    // Add to DOM
    document.body.appendChild(modal);

    // Add event listeners
    modal.addEventListener('click', function(e) {
      if (e.target === modal) {
        modal.remove();
      }
    });

    document.getElementById('close-modal').addEventListener('click', function() {
      modal.remove();
    });

    // Close on Escape key
    const handleEscape = function(e) {
      if (e.key === 'Escape') {
        modal.remove();
        document.removeEventListener('keydown', handleEscape);
      }
    };
    document.addEventListener('keydown', handleEscape);
  }

  /**
   * Initialize citation click handlers using event delegation
   */
  function initializeCitationHandlers() {
    // Remove existing handlers to prevent duplicates
    document.removeEventListener('click', globalCitationClickHandler);
    
    // Add global click handler for citation links
    document.addEventListener('click', globalCitationClickHandler);
  }

  /**
   * Global citation click handler
   * @param {Event} e - Click event
   */
  function globalCitationClickHandler(e) {
    const target = e.target.closest('.session-citation-link');
    if (target) {
      const sourceId = target.getAttribute('data-source-id');
      if (sourceId) {
        handleSessionCitationClick(sourceId);
      }
    }
  }

  /**
   * Fallback sources when registration fails
   * @param {Array} sources - Original sources
   * @returns {Array} - Sources with fallback IDs
   */
  function fallbackSources(sources) {
    return sources.map((source, index) => ({
      ...source,
      id: source.id || `fallback_${index + 1}`,
      display_id: String(index + 1),
      session_id: sessionId,
      hash: `fallback_${index + 1}`
    }));
  }

  /**
   * HTML escaping utility
   * @param {string} unsafe - Unsafe string
   * @returns {string} - Escaped string
   */
  function escapeHtml(unsafe) {
    if (typeof unsafe !== 'string') {
      return String(unsafe || '');
    }
    
    const div = document.createElement('div');
    div.textContent = unsafe;
    return div.innerHTML;
  }

  /**
   * Get citation statistics for debugging
   * @returns {Promise<Object>} - Citation statistics
   */
  async function getCitationStats() {
    try {
      const response = await fetch(`/api/session-citations/stats?session_id=${sessionId}`);
      const result = await response.json();
      return result.success ? result.stats : {};
    } catch (error) {
      console.error('Error getting citation stats:', error);
      return {};
    }
  }

  /**
   * Clear all session citations
   * @returns {Promise<boolean>} - Success status
   */
  async function clearSessionCitations() {
    try {
      const response = await fetch('/api/session-citations/clear', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId })
      });
      
      const result = await response.json();
      
      if (result.success) {
        citationCache.clear();
        console.log('Session citations cleared');
        return true;
      } else {
        console.warn('Failed to clear session citations:', result.error);
        return false;
      }
      
    } catch (error) {
      console.error('Error clearing session citations:', error);
      return false;
    }
  }

  // Initialize when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeSessionCitationSystem);
  } else {
    initializeSessionCitationSystem();
  }

  // Export to global scope
  window.SessionCitationSystem = {
    registerSources,
    getSourceById,
    // Backward compatibility
    getSourceByCitationId: getSourceById,
    formatTextWithCitations,
    generateSourcesSection,
    handleSessionCitationClick,
    getCitationStats,
    clearSessionCitations,
    escapeHtml,
    
    // Debug utilities
    enableDebug: () => {
      debugMode = true;
      localStorage.setItem('citation-debug', 'true');
      console.log('Citation debug mode enabled');
    },
    disableDebug: () => {
      debugMode = false;
      localStorage.removeItem('citation-debug');
      console.log('Citation debug mode disabled');
    },
    getCache: () => citationCache,
    getSessionId: () => sessionId
  };

  // Make handleSessionCitationClick available globally for onclick attributes
  window.handleSessionCitationClick = handleSessionCitationClick;

  console.log('Session Citation System loaded');

})();
