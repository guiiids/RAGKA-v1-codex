from flask import Flask, request, jsonify, render_template, send_from_directory
from flask_cors import CORS
import json
import logging
import sys
import os
import time
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)
if logger.handlers:
    logger.handlers.clear()

file_handler = logging.FileHandler('app.log')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)
logger.setLevel(logging.DEBUG)

logger.info("Chatbot Tools Dashboard starting up")

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Routes for the main dashboard
@app.route('/')
def index():
    """Serve the main dashboard homepage"""
    return render_template('index.html')

@app.route('/prompt-evaluator')
def prompt_evaluator():
    """Serve the Prompt Evaluator tool"""
    return render_template('prompt_evaluator.html')

@app.route('/prompt-lab')
def prompt_lab():
    """Serve the Prompt Lab with enhancement widgets"""
    return render_template('prompt_lab.html')

@app.route('/feedback-insights')
def feedback_insights():
    """Serve the Feedback Insights dashboard"""
    return render_template('feedback_insights.html')

# API Routes
@app.route('/api/evaluate-prompt', methods=['POST'])
def evaluate_prompt():
    """Evaluate a prompt and return analysis"""
    try:
        data = request.get_json()
        
        if not data or 'prompt' not in data:
            return jsonify({'error': 'Prompt is required'}), 400
        
        prompt_text = data['prompt']
        
        logger.info(f"Evaluating prompt: {prompt_text[:100]}...")
        
        # Mock evaluation logic - replace with actual evaluation
        evaluation = {
            'clarity_score': 85,
            'specificity_score': 78,
            'completeness_score': 92,
            'overall_score': 85,
            'suggestions': [
                'Consider adding more specific context',
                'Define the expected output format',
                'Include examples for better clarity'
            ],
            'strengths': [
                'Clear objective stated',
                'Good use of descriptive language',
                'Appropriate length'
            ],
            'weaknesses': [
                'Could be more specific about requirements',
                'Missing context about target audience'
            ],
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info("Prompt evaluation completed successfully")
        return jsonify(evaluation)
        
    except Exception as e:
        logger.error(f"Error evaluating prompt: {e}")
        return jsonify({
            'error': str(e),
            'status': 'error',
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/enhance-prompt', methods=['POST'])
def enhance_prompt():
    """Enhance a prompt with suggestions"""
    try:
        data = request.get_json()
        
        if not data or 'prompt' not in data:
            return jsonify({'error': 'Prompt is required'}), 400
        
        prompt_text = data['prompt']
        enhancement_type = data.get('type', 'general')
        
        logger.info(f"Enhancing prompt: {prompt_text[:100]}...")
        
        # Mock enhancement logic - replace with actual enhancement
        enhanced_prompt = f"Enhanced version: {prompt_text} [Please provide specific examples and context for better results]"
        
        enhancement_result = {
            'original_prompt': prompt_text,
            'enhanced_prompt': enhanced_prompt,
            'enhancement_type': enhancement_type,
            'improvements': [
                'Added request for specific examples',
                'Included context requirement',
                'Improved clarity of instructions'
            ],
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info("Prompt enhancement completed successfully")
        return jsonify(enhancement_result)
        
    except Exception as e:
        logger.error(f"Error enhancing prompt: {e}")
        return jsonify({
            'error': str(e),
            'status': 'error',
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/rephrase-prompt', methods=['POST'])
def rephrase_prompt():
    """Rephrase a prompt with different variations"""
    try:
        data = request.get_json()
        
        if not data or 'prompt' not in data:
            return jsonify({'error': 'Prompt is required'}), 400
        
        prompt_text = data['prompt']
        style = data.get('style', 'professional')
        
        logger.info(f"Rephrasing prompt: {prompt_text[:100]}...")
        
        # Mock rephrasing logic - replace with actual rephrasing
        variations = [
            f"Professional version: {prompt_text}",
            f"Casual version: {prompt_text}",
            f"Technical version: {prompt_text}"
        ]
        
        rephrase_result = {
            'original_prompt': prompt_text,
            'variations': variations,
            'style': style,
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info("Prompt rephrasing completed successfully")
        return jsonify(rephrase_result)
        
    except Exception as e:
        logger.error(f"Error rephrasing prompt: {e}")
        return jsonify({
            'error': str(e),
            'status': 'error',
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/feedback-data', methods=['GET'])
def get_feedback_data():
    """Get feedback insights data"""
    try:
        # Mock feedback data - replace with actual data source
        feedback_data = {
            'total_responses': 1247,
            'positive_feedback': 892,
            'negative_feedback': 355,
            'satisfaction_rate': 71.5,
            'common_issues': [
                {'issue': 'Response too generic', 'count': 89},
                {'issue': 'Missing context', 'count': 67},
                {'issue': 'Incorrect information', 'count': 45},
                {'issue': 'Too verbose', 'count': 34},
                {'issue': 'Unclear instructions', 'count': 28}
            ],
            'feedback_trends': [
                {'date': '2025-06-01', 'positive': 45, 'negative': 12},
                {'date': '2025-06-02', 'positive': 52, 'negative': 8},
                {'date': '2025-06-03', 'positive': 38, 'negative': 15},
                {'date': '2025-06-04', 'positive': 41, 'negative': 11},
                {'date': '2025-06-05', 'positive': 48, 'negative': 9},
                {'date': '2025-06-06', 'positive': 44, 'negative': 13}
            ],
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info("Feedback data retrieved successfully")
        return jsonify(feedback_data)
        
    except Exception as e:
        logger.error(f"Error retrieving feedback data: {e}")
        return jsonify({
            'error': str(e),
            'status': 'error',
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/submit-feedback', methods=['POST'])
def submit_feedback():
    """Submit user feedback"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'Feedback data is required'}), 400
        
        feedback_type = data.get('type', 'general')
        rating = data.get('rating')
        comment = data.get('comment', '')
        
        logger.info(f"Submitting feedback: {feedback_type}, rating: {rating}")
        
        # Mock feedback submission - replace with actual storage
        feedback_result = {
            'status': 'success',
            'message': 'Feedback submitted successfully',
            'feedback_id': f"fb_{int(time.time())}",
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info("Feedback submitted successfully")
        return jsonify(feedback_result)
        
    except Exception as e:
        logger.error(f"Error submitting feedback: {e}")
        return jsonify({
            'error': str(e),
            'status': 'error',
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'chatbot-tools-dashboard',
        'timestamp': datetime.now().isoformat()
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    port = 5004
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    logger.info(f"Starting Chatbot Tools Dashboard on port {port} with debug={debug}")
    
    app.run(host='0.0.0.0', port=port, debug=debug)

