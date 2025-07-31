"""
Alternate version of main.py that uses the improved RAG implementation
"""
print("Running:", __file__)

import ssl
ssl._create_default_https_context = ssl._create_unverified_context

import requests
requests.packages.urllib3.disable_warnings()
requests.sessions.Session.verify = False

import traceback
from flask import Flask, request, jsonify, render_template, Response, send_from_directory, session
import json
import logging
import sys
import os
from logging.handlers import RotatingFileHandler
from pythonjsonlogger import jsonlogger
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify, render_template_string, Response, send_from_directory, session


load_dotenv()


def get_sas_token():
    return os.getenv("SAS_TOKEN")

load_dotenv() 
sas_token = os.getenv("SAS_TOKEN", "")

# Import the improved RAG implementation
from rag_assistant_v2 import FlaskRAGAssistantV2
from db_manager import DatabaseManager
from openai import AzureOpenAI
from config import get_cost_rates
from openai_service import OpenAIService
from rag_improvement_logging import setup_improvement_logging

# Set up dedicated logging for the improved implementation
logger = setup_improvement_logging()

# Add file handler with absolute path for main application logs
file_handler = logging.FileHandler('logs/main_alternate.log')
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Stream logs to stdout for visibility
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setLevel(logging.INFO)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

logger.info("Alternate Flask RAG application starting up with improved procedural content handling")

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "default-secret-key-for-sessions")


# Dictionary to store RAG assistant instances by session ID
rag_assistants = {}

# Function to get or create a RAG assistant for a session
def get_rag_assistant(session_id):
    """Get or create a RAG assistant for the given session ID"""
    if session_id not in rag_assistants:
        logger.info(f"Creating new RAG assistant for session {session_id}")
        rag_assistants[session_id] = FlaskRAGAssistantV2()
    return rag_assistants[session_id]

# HTML template with Tailwind CSS - same as in main.py
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SAGE Knowledge Navigator (Improved)</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
  <script src="/static/js/marked-renderer.js"></script>
   <script src="/static/js/feedback-integration.js"></script>
  <style id="custom-styles">
    /* Same styles as in main.py */
    .avatar {
      width: 48px;
      height: 48px;
      object-fit: cover;
      border-radius: 50%;
    }
    body, html {
      height: 100%;
      margin: 0;
      padding: 0;
      overflow: hidden;
    }
    .chat-container {
      display: flex;
      flex-direction: column;
      height: 100vh;
    }
    .chat-messages {
      flex-grow: 1;
      overflow-y: auto;
      padding: 1rem;
    }
    .chat-input {
      padding: 1rem;
      background-color: white;
    }
    .user-message {
      display: flex;
      justify-content: flex-end;
      flex-direction: row-reverse;
      margin-bottom: 1rem;
      width: 100%;
    }
    .bot-message {
      display: flex;
      justify-content: flex-start;
      margin-bottom: 1rem;
      width: 100%;
    }
    .message-bubble {
      display: inline-block;
      width: auto;
      padding: 0.75rem 1rem;
      border-radius: 1rem;
    }
    .user-bubble {
      border-bottom-right-radius: 0.25rem;
      margin-left: 1rem;
      align-self: flex-end;
    }
    .bot-bubble {
      background-color: #fffff;
      color: black;
    }
    .bot-bubble ul {
      list-style-type: disc;
      padding-left: 1.5rem;
    }
    .bot-bubble a {
      color: blue;
      text-decoration: underline;
      cursor: pointer;
    }
    .hidden {
      display: none !important;
    }
  </style>
</head>
<body class="bg-white dark:bg-black">
  <div class="chat-container w-[60%] mx-auto">
    <!-- Header -->
    <div class="bg-white dark:bg-black text-white border-b-2 border-gray-100 dark: border-white/30 px-4 py-3 flex items-center justify-between">
      <div class="flex items-center">
        <img id="nav-logo" class="h-auto max-w-sm w-auto inline-block object-cover max-h-6" alt="Logo" src="https://content.tst-34.aws.agilent.com/wp-content/uploads/2025/06/5.png">
        <span class="ml-2 text-black font-bold">IMPROVED RAG</span>
      </div>
    </div>
    
    <!-- Chat Messages Area -->
    <div id="chat-messages" class="chat-messages">
      <!-- Logo centered in message area before first message -->
      <div id="center-logo" class="flex flex-col items-center justify-center h-full ">
        <img id="random-logo" class="h-160 w-auto inline-block object-cover md:h-80" alt="Logo" src="/assets/">
      </div>

      <!-- Bot welcome message (initially hidden) -->
      <div id="welcome-message" class="flex items-start gap-2.5 mb-4 hidden">
        <img class="w-8 h-8 rounded-full" src="https://content.tst-34.aws.agilent.com/wp-content/uploads/2025/05/dalle.png" alt="AI Agent">
        <div class="flex flex-col w-auto max-w-[90%] leading-1.5">
          <div class="flex items-center space-x-2 rtl:space-x-reverse">
            <span class="text-sm font-semibold text-gray-900 dark:text-white/80 ">SAGE<span class="mt-1 text-sm leading-tight font-medium text-blue-700 dark:text-white/80">AI Agent</span></span>
          </div>
          <div class="text-sm font-normal py-2 text-gray-900 ">
            Hi there! I'm an AI assistant trained on your knowledge base. What would you like to know?
          </div>
        </div>
      </div>
      <!-- Messages will be added here dynamically -->
    </div>
    
    <!-- Chat Input Area -->
    <div class="chat-input bg-white dark:bg-black text-gray-900 dark:text-white">
      <div class="relative rounded-3xl border border-gray-300 p-4 bg-white dark:bg-black text-gray-900 dark:text-white max-w-3xl mx-auto mt-10 shadow-md">
        <div class="flex items-center space-x-2">
          <!-- Dynamic textarea -->
          <textarea
            id="query-input"
            rows="1"
            placeholder="Type here..."
            class="flex-grow resize-none overflow-hidden text-sm text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 leading-relaxed outline-none bg-transparent"
            oninput="this.style.height = 'auto'; this.style.height = (this.scrollHeight) + 'px';"
            style="min-height: 34px;"
          ></textarea>
          <button
            id="submit-btn"
            class="rounded-2xl bg-gradient-to-r from-blue-800 to-blue-400 py-2 px-4 border border-transparent text-center text-sm text-white transition-all shadow-sm hover:opacity-90 focus:opacity-95 focus:shadow-none active:opacity-95 disabled:pointer-events-none disabled:opacity-50 disabled:shadow-none"
            type="button"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  </div>

  <!-- Utility functions and base chat functionality -->
  <script>
    // --- Utility Functions ---
    function escapeHtml(unsafe) {
      return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
    }
    
    function formatMessage(message) {
      // Convert URLs to links
      message = message.replace(
        /(https?:\/\/[^\s]+)/g, 
        '<a href="$1" target="_blank" class="text-blue-600 hover:underline">$1</a>'
      );
      // Convert **bold** to <strong>
      message = message.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
      // Convert *italic* to <em>
      message = message.replace(/\*(.*?)\*/g, '<em>$1</em>');
      // Convert newlines to <br>
      message = message.replace(/\\n/g, '<br>');
      // Convert citation references [n] to clickable links
      message = message.replace(
        /\[(\d+)\]/g,
        '<a href="#source-$1" class="citation-link text-xs text-blue-600 hover:underline" data-source-id="$1">[$1]</a>'
      );
      return message;
    }

    // --- DOM elements ---
    const chatMessages = document.getElementById('chat-messages');
    const queryInput = document.getElementById('query-input');
    const submitBtn = document.getElementById('submit-btn');
    
    // Auto-resize textarea up to 6 lines
    const maxLines = 6;
    const lineHeight = parseInt(window.getComputedStyle(queryInput).lineHeight);
    queryInput.addEventListener('input', () => {
      queryInput.style.height = 'auto';
      const boundedHeight = Math.min(queryInput.scrollHeight, lineHeight * maxLines);
      queryInput.style.height = boundedHeight + 'px';
      queryInput.style.overflowY = queryInput.scrollHeight > lineHeight * maxLines ? 'auto' : 'hidden';
    });
    
    // --- Chat functionality ---
    // Add user message to chat
    function addUserMessage(message) {
      // Hide center logo if visible
      const centerLogo = document.getElementById('center-logo');
      if (centerLogo && !centerLogo.classList.contains('hidden')) {
        centerLogo.classList.add('hidden');
      }
      
      // Create message element
      const messageDiv = document.createElement('div');
      messageDiv.className = 'user-message';
      messageDiv.innerHTML = `
        <img class="w-8 h-8 rounded-full" src="https://content.tst-34.aws.agilent.com/wp-content/uploads/2025/05/Untitled-design-3.png" alt="AI Agent">
        <div class="flex flex-col items-end w-full max-w-[90%] leading-1.5">
          <div class="flex items-center space-x-2 rtl:space-x-reverse pr-1 pb-1">
            <span class="text-xs font-semibold text-gray-900 dark:text-white/80"><span class="mt-1 text-xs leading-tight font-medium text-blue-700 dark:text-white/80">ME</span></span>
          </div>
          <div class="text-sm font-normal py-2 text-gray-900 dark:text-white/80 message-bubble user-bubble">
             ${formatMessage(message)}
          </div>
        </div>
      `;
    
      // Add to chat
      chatMessages.appendChild(messageDiv);
      chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    
    // Add bot message to chat
    function addBotMessage(message) {
      // Hide center logo if visible
      const centerLogo = document.getElementById('center-logo');
      if (centerLogo && !centerLogo.classList.contains('hidden')) {
        centerLogo.classList.add('hidden');
      }
      
      // Create message element
      const messageDiv = document.createElement('div');
      messageDiv.className = 'bot-message';
      messageDiv.innerHTML = `
        <img class="w-8 h-8 rounded-full" src="https://content.tst-34.aws.agilent.com/wp-content/uploads/2025/05/dalle.png" alt="AI Agent">
        <div class="flex flex-col w-auto max-w-[90%] leading-1.5">
          <div class="flex items-center space-x-2 rtl:space-x-reverse pl-1 pb-1">
            <span class="text-xs font-semibold text-gray-900 dark:text-white ">SAGE<span class="mt-1 text-xs leading-tight font-strong text-blue-700 dark:text-white/80"> AI Agent</span></span>
          </div>
          <div class="text-sm leading-6 font-normal py-2 text-gray-900 dark:text-white/80 message-bubble bot-bubble">
             ${formatMessage(message)}
          </div>
          <span class="text-xs font-normal text-gray-500 dark:text-white/60 text-right pt-33" data-message-id="{{ messageId }}">Was this helpful?</span>
        </div>
      `;
    
      // Add to chat
      chatMessages.appendChild(messageDiv);
      chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    
    // Add typing indicator
    function addTypingIndicator() {
      const indicatorDiv = document.createElement('div');
      indicatorDiv.className = 'bot-message';
      indicatorDiv.innerHTML = `
        <img class="avatar" src="https://content.tst-34.aws.agilent.com/wp-content/uploads/2025/05/dalle.png" alt="AI">
        <div class="typing-indicator">
          <span></span><span></span><span></span>
        </div>
      `;
      
      chatMessages.appendChild(indicatorDiv);
      chatMessages.scrollTop = chatMessages.scrollHeight;
      
      return indicatorDiv;
    }
    
    // Basic input handling
    if (queryInput && submitBtn) {
      // Enable submit button on input
      queryInput.addEventListener('keydown', function(e) {
        submitBtn.disabled = false;
        if (e.key === 'Enter' && !e.shiftKey) {
          e.preventDefault();
          submitBtn.click();
        }
      });
      
      // Submit button click handler
      submitBtn.addEventListener('click', function() {
        submitQuery();
      });
    }
    
    // Standard query submission
    function submitQuery() {
      const query = queryInput.value.trim();
      if (!query) return;
      
      addUserMessage(query);
      queryInput.value = '';
      
      // Show typing indicator
      const typingIndicator = addTypingIndicator();
      
      // Call API to get response
      fetch('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: query })
      })
      .then(response => response.json())
      .then(data => {
        // Remove typing indicator
        if (typingIndicator) typingIndicator.remove();
        
        // Show response
        if (data.error) {
          addBotMessage('Error: ' + data.error);
        } else {
          addBotMessage(data.answer);
          
          // Show sources if available
          if (data.sources && data.sources.length > 0) {
            // Store last sources for citation click handling
            window.lastSources = data.sources;
            // Add sources utilized section
            addSourcesUtilizedSection();
          }
        }
      })
      .catch(error => {
        // Remove typing indicator
        if (typingIndicator) typingIndicator.remove();
        
        // Show error
        addBotMessage('Error: Could not connect to server. Please try again later.');
        console.error('Error:', error);
      });
    }
    
    // Add sources utilized section function
    function addSourcesUtilizedSection() {
      if (window.lastSources && window.lastSources.length > 0) {
        let sourcesHtml = '<div class="sources-section mt-4 pt-3 border-t border-gray-200">';
        sourcesHtml += '<h4 class="text-sm font-semibold text-gray-700 mb-2">Sources Utilized</h4>';
        sourcesHtml += '<ol class="text-sm text-gray-600 space-y-1 pl-4">';
        
        window.lastSources.forEach((source, index) => {
          let sourceTitle = 'Untitled Source';
          
          if (typeof source === 'string') {
            // If source is just a string, use it as the title (truncated)
            sourceTitle = source.length > 80 ? source.substring(0, 80) + '...' : source;
          } else if (typeof source === 'object' && source !== null) {
            // If source is an object, try to get title, otherwise use content or fallback
            sourceTitle = source.title || 
                         (source.content ? (source.content.length > 80 ? source.content.substring(0, 80) + '...' : source.content) : 
                         `Source ${index + 1}`);
          }
          
          // Escape HTML in the title to prevent XSS
          sourceTitle = escapeHtml(sourceTitle);
          
          // Make the source title clickable with the same functionality as inline citations
          sourcesHtml += `<li>${index + 1}. <a href="#source-${index + 1}"
            class="citation-link text-blue-600 hover:underline cursor-pointer" data-source-id="${index + 1}">${sourceTitle}</a></li>`;
        });
        
        sourcesHtml += '</ol>';
        sourcesHtml += '</div>';
        
        // Append to the last bot message
        const lastBotMessage = document.querySelector('.bot-message:last-child .message-bubble');
        if (lastBotMessage) {
          lastBotMessage.innerHTML += sourcesHtml;
        }
      }
    }
  </script>
</body>
</html>
"""


@app.route("/", methods=["GET"])
def index():
    logger.info("Index page accessed")
    # Generate a session ID if one doesn't exist
    if 'session_id' not in session:
        session['session_id'] = os.urandom(16).hex()
        logger.info(f"New session created: {session['session_id']}")
    
    return render_template_string(HTML_TEMPLATE, sas_token=sas_token)

@app.route("/api/query", methods=["POST"])
def api_query():
    data = request.get_json()
    logger.info("DEBUG - Incoming /api/query payload: %s", json.dumps(data))
    user_query = data.get("query", "")
    is_enhanced = data.get("is_enhanced", False)
    logger.info(f"API query received: {user_query}")
    
    # Get the session ID
    session_id = session.get('session_id')
    if not session_id:
        session_id = os.urandom(16).hex()
        session['session_id'] = session_id
        logger.info(f"Created new session ID: {session_id}")
    
    # Extract any settings from the request
    settings = data.get("settings", {})
    logger.info(f"DEBUG - Request settings: {json.dumps(settings)}")
    
    try:
        # Get or create the RAG assistant for this session
        rag_assistant = get_rag_assistant(session_id)
        
        # Update settings if provided
        if settings:
            for key, value in settings.items():
                if hasattr(rag_assistant, key):
                    setattr(rag_assistant, key, value)
            
            # If model is updated, update the deployment name
            if "model" in settings:
                rag_assistant.deployment_name = settings["model"]
        
        logger.info(f"DEBUG - Using model: {rag_assistant.deployment_name}")
        logger.info(f"DEBUG - Temperature: {rag_assistant.temperature}")
        logger.info(f"DEBUG - Max tokens: {rag_assistant.max_completion_tokens}")
        logger.info(f"DEBUG - Top P: {rag_assistant.top_p}")
        
        answer, cited_sources, _, evaluation, context = rag_assistant.generate_rag_response(user_query, is_enhanced=is_enhanced)
        logger.info(f"API query response generated for: {user_query}")
        logger.info(f"DEBUG - Response length: {len(answer)}")
        logger.info(f"DEBUG - Number of cited sources: {len(cited_sources)}")
        
        try:
            # Log using existing log_rag_query method by unpacking relevant fields
            vote_id = DatabaseManager.log_rag_query(
                query=user_query,
                response=answer,
                sources=cited_sources,
                context=context,
                sql_query=None
            )
            logger.info(f"RAG query logged with ID: {vote_id}")
        except Exception as log_exc:
            logger.error(f"Failed to log RAG query: {log_exc}", exc_info=True)
        
        return jsonify({
            "answer": answer,
            "sources": cited_sources,
            "evaluation": evaluation
        })
    except Exception as e:
        logger.error(f"Error in api_query: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            "error": str(e)
        }), 500

@app.route("/api/clear_history", methods=["POST"])
def api_clear_history():
    """Clear the conversation history for the current session"""
    try:
        session_id = session.get('session_id')
        if session_id and session_id in rag_assistants:
            logger.info(f"Clearing conversation history for session {session_id}")
            rag_assistants[session_id].clear_conversation_history()
            return jsonify({"success": True})
        else:
            logger.warning(f"No active session found to clear history")
            return jsonify({"success": True, "message": "No active session found"})
    except Exception as e:
        logger.error(f"Error clearing conversation history: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({"success": False, "error": str(e)}), 500

# Serve static files from the 'static' folder
@app.route("/static/<path:filename>")
def serve_static(filename):
    return send_from_directory("static", filename)

# Serve static files from the 'assets' folder
@app.route("/assets/<path:filename>")
def serve_assets(filename):
    return send_from_directory("assets", filename)

# Feedback submission endpoint
@app.route("/api/feedback", methods=["POST"])
def api_feedback():
    data = request.get_json()
    logger.debug("Incoming feedback payload: %s", json.dumps(data))
    try:
        vote_id = DatabaseManager.save_feedback(data)
        logger.info(f"Feedback saved with ID: {vote_id}")
        # Fallback: write feedback to local JSON file
        with open("logs/feedback_fallback.jsonl", "a") as f:
            f.write(json.dumps({"vote_id": vote_id, **data}) + "\n")
        return jsonify({"success": True, "vote_id": vote_id})
    except Exception as e:
        logger.error("Error saving feedback: %s", str(e), exc_info=True)
        # Fallback: write raw feedback to local JSON file
        with open("logs/feedback_fallback.jsonl", "a") as f:
            f.write(json.dumps(data) + "\n")
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Run the Improved Flask RAG application')
    parser.add_argument('--port', type=int, default=int(os.environ.get("PORT", 5004)),
                        help='Port to run the server on (default: 5004)')
    args = parser.parse_args()
    
    port = args.port
    logger.info(f"Starting Improved Flask app on port {port}")

    app.run(host="0.0.0.0", port=port, debug=True)
