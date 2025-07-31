"""
GPT-4 based intent classification system.
"""
import logging
import os
from typing import Dict, List, Tuple, Optional
import json
from openai_service import OpenAIService
from enhanced_pattern_matcher import EnhancedPatternMatcher

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GPT4IntentClassifier:
    """Intent classifier using GPT-4 for natural language understanding."""
    
    def __init__(
        self,
        use_fallback: bool = True,
        azure_endpoint: str = None,
        api_key: str = None,
        api_version: str = None,
        deployment_name: str = None
    ):
        """
        Initialize the classifier.
        
        Args:
            use_fallback: Whether to use regex classifier as fallback
            azure_endpoint: Azure OpenAI endpoint URL
            api_key: Azure OpenAI API key
            api_version: API version to use
            deployment_name: Model deployment name
        """
        # Use environment variables if not provided
        self.azure_endpoint = azure_endpoint or os.getenv('AZURE_OPENAI_ENDPOINT')
        self.api_key = api_key or os.getenv('AZURE_OPENAI_KEY')
        self.api_version = api_version or os.getenv('AZURE_OPENAI_API_VERSION_O4_MINI', '2024-12-01-preview')
        self.deployment_name = deployment_name or os.getenv('CHAT_DEPLOYMENT_O4_MINI')
        
        # Initialize OpenAI client
        self.openai_client = OpenAIService(
            azure_endpoint=self.azure_endpoint,
            api_key=self.api_key,
            api_version=self.api_version,
            deployment_name=self.deployment_name
        )
        
        self.fallback_classifier = EnhancedPatternMatcher() if use_fallback else None
        
        # Valid classification types
        self.valid_types = {
            'NEW_TOPIC_INFORMATIONAL',
            'NEW_TOPIC_PROCEDURAL',
            'CONTEXTUAL_FOLLOW_UP',
            'HISTORY_RECALL'
        }
        
        # NEW: Dynamic confidence thresholds
        self.confidence_thresholds = {
            'gpt4_fallback': 0.5,      # Current threshold
            'regex_override': 0.8,     # High-confidence regex overrides GPT-4
            'quick_classification': 0.85  # Confidence for quick checks
        }
        
        # NEW: Performance tracking
        self.performance_stats = {
            'gpt4_calls': 0,
            'regex_fallbacks': 0,
            'quick_classifications': 0,
            'total_queries': 0
        }
    
    def _format_history(self, history: List[Dict]) -> str:
        """Format conversation history for the prompt."""
        if not history:
            return "No previous conversation context."
        
        formatted = []
        for msg in history[-3:]:  # Only use last 3 messages for context
            role = msg.get('role', '').upper()
            content = msg.get('content', '').strip()
            formatted.append(f"{role}: {content}")
        
        return "\n".join(formatted)
    
    def _validate_classification(
        self,
        classification: str,
        confidence: float
    ) -> Tuple[bool, str]:
        """Validate the classification and confidence."""
        if not classification or classification not in self.valid_types:
            return False, "Invalid classification type"
        
        try:
            conf = float(confidence)
            if not (0 <= conf <= 1):
                return False, "Confidence must be between 0 and 1"
        except (ValueError, TypeError):
            return False, "Invalid confidence value"
        
        return True, ""
    
    def _quick_classification_check(
        self,
        query: str,
        conversation_history: Optional[List[Dict]] = None
    ) -> Optional[Tuple[str, float]]:
        """Quick classification for obvious cases to avoid GPT-4 calls."""
        
        # Very short queries with history are likely follow-ups
        if len(query.split()) <= 2 and conversation_history:
            short_followups = ['why', 'how', 'what', 'when', 'where', 'more', 'yes', 'no']
            if any(word.lower() in query.lower() for word in short_followups):
                self.performance_stats['quick_classifications'] += 1
                return 'CONTEXTUAL_FOLLOW_UP', self.confidence_thresholds['quick_classification']
        
        # Obvious procedural patterns
        if query.lower().startswith(('how to', 'how do i', 'how can i', 'steps to')):
            self.performance_stats['quick_classifications'] += 1
            return 'NEW_TOPIC_PROCEDURAL', 0.95
        
        # Obvious informational patterns  
        if query.lower().startswith(('what is', 'what are', 'tell me about', 'explain')):
            self.performance_stats['quick_classifications'] += 1
            return 'NEW_TOPIC_INFORMATIONAL', 0.95
        
        # Obvious history recall
        if any(phrase in query.lower() for phrase in ['what did i', 'what was my', 'earlier we']):
            self.performance_stats['quick_classifications'] += 1
            return 'HISTORY_RECALL', 0.9
        
        return None  # Proceed to GPT-4

    def classify_query(
        self,
        query: str,
        conversation_history: Optional[List[Dict]] = None
    ) -> Tuple[str, float]:
        """
        Classify the query using GPT-4 with pre-filtering optimization.
        
        Args:
            query: The user's query
            conversation_history: Optional list of previous conversation turns
            
        Returns:
            Tuple of (query_type, confidence_score)
        """
        # Track total queries
        self.performance_stats['total_queries'] += 1
        
        try:
            # NEW: Pre-GPT-4 quick checks
            quick_result = self._quick_classification_check(query, conversation_history)
            if quick_result:
                logger.info(f"Quick classification: {quick_result[0]} with confidence {quick_result[1]:.2f}")
                return quick_result
            
            # Continue with GPT-4 logic
            self.performance_stats['gpt4_calls'] += 1
            
            # Format the conversation history
            context = self._format_history(conversation_history) if conversation_history else "No previous context"
            
            # Construct the prompt
            prompt = f"""Given this conversation history:
{context}

And this new query: "{query}"

Classify the query as exactly one of these types:
NEW_TOPIC_INFORMATIONAL - Asking about what something is
NEW_TOPIC_PROCEDURAL - Asking how to do something
CONTEXTUAL_FOLLOW_UP - Following up on previous topic
HISTORY_RECALL - Referring to earlier conversation

Return only two lines:
1. The classification
2. Confidence score (0.0-1.0)"""

            # Get GPT-4 response
            response = self.openai_client.get_chat_response(
                messages=[{"role": "user", "content": prompt}],
                max_completion_tokens=20
            )
            
            # Parse response
            lines = response.strip().split('\n')
            if len(lines) != 2:
                raise ValueError("Invalid response format")
            
            classification = lines[0].strip()
            confidence = float(lines[1].strip())
            
            # Validate the results
            is_valid, error = self._validate_classification(classification, confidence)
            if not is_valid:
                raise ValueError(error)
            
            logger.info(f"GPT-4 classified query '{query}' as {classification} "
                       f"with confidence {confidence:.2f}")
            
            # Fallback to regex for low-confidence follow-up
            if confidence < 0.5 and self.fallback_classifier:
                fallback_type, fallback_conf = self.fallback_classifier.classify_query(query, conversation_history)
                if fallback_type == 'CONTEXTUAL_FOLLOW_UP':
                    logger.info(f"Using fallback classification: {fallback_type} with confidence {fallback_conf:.2f}")
                    return fallback_type, fallback_conf
                if fallback_conf > confidence:
                    logger.info(f"Using higher-confidence fallback: {fallback_type} with confidence {fallback_conf:.2f}")
                    return fallback_type, fallback_conf
            
            return classification, confidence
            
        except Exception as e:
            logger.error(f"GPT-4 classification failed: {e}")
            
            # Use fallback if available
            if self.fallback_classifier:
                logger.info("Using regex fallback classifier")
                return self.fallback_classifier.classify_query(query, conversation_history)
            
            # Default response if no fallback
            return 'NEW_TOPIC_INFORMATIONAL', 0.5
    
    def get_confidence_explanation(
        self,
        query: str,
        query_type: str,
        confidence: float
    ) -> str:
        """
        Get a human-readable explanation of the confidence score.
        
        Args:
            query: The original query
            query_type: The detected query type
            confidence: The confidence score
            
        Returns:
            A string explaining the classification
        """
        explanation = [
            f"Classification of query: '{query}'",
            f"Detected type: {query_type}",
            f"Confidence score: {confidence:.2f}",
            "Method: GPT-4 natural language understanding"
        ]
        
        return "\n".join(explanation)
    
    def get_performance_stats(self) -> Dict[str, float]:
        """Get performance statistics for monitoring."""
        total = self.performance_stats['total_queries']
        if total == 0:
            return {}
        
        return {
            'gpt4_call_rate': self.performance_stats['gpt4_calls'] / total,
            'regex_fallback_rate': self.performance_stats['regex_fallbacks'] / total,
            'quick_classification_rate': self.performance_stats['quick_classifications'] / total,
            'api_cost_reduction': 1 - (self.performance_stats['gpt4_calls'] / total),
            'total_queries': total
        }
