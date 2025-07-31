"""
Enhanced conversation context analysis for improved query classification.
"""
from typing import Dict, List, Optional, Tuple
import logging
from enhanced_patterns import get_context_indicators

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ConversationContextAnalyzer:
    """Analyzes conversation context to improve query classification."""
    
    def __init__(self):
        self.context_indicators = get_context_indicators()
        
        # Weights for different context signals
        self.weights = {
            'temporal_reference': 0.5,  # Increased weight for temporal references
            'continuation_marker': 0.25,
            'topic_shift': 0.2,
            'query_length': 0.15,
            'conversation_depth': 0.2  # Increased weight for conversation depth
        }
        
        # Thresholds
        self.short_query_threshold = 3  # words
        self.deep_conversation_threshold = 5  # turns
    
    def analyze_context(
        self,
        query: str,
        conversation_history: Optional[List[Dict]] = None
    ) -> Dict[str, float]:
        """
        Analyze conversation context to improve query classification.
        
        Args:
            query: The current user query
            conversation_history: Optional list of previous conversation turns
            
        Returns:
            Dictionary of context scores for each query type
        """
        # Initialize scores for each query type
        context_scores = {
            'HISTORY_RECALL': 0.0,
            'CONTEXTUAL_FOLLOW_UP': 0.0,
            'NEW_TOPIC_PROCEDURAL': 0.0,
            'NEW_TOPIC_INFORMATIONAL': 0.0
        }
        
        # Handle empty or very short queries
        query_words = query.strip().split()
        if not query_words:
            return context_scores
            
        # If single word or very short query and we have history, likely a follow-up
        if len(query_words) <= 2 and conversation_history:
            context_scores['CONTEXTUAL_FOLLOW_UP'] = 0.7
            return context_scores
            
        # If no history, likely a new topic
        if not conversation_history:
            context_scores['NEW_TOPIC_INFORMATIONAL'] = 0.6
            context_scores['NEW_TOPIC_PROCEDURAL'] = 0.4
            return context_scores
        
        # Get basic context signals
        temporal_signals = self._check_temporal_references(query)
        continuation_signals = self._check_continuation_markers(query)
        topic_shift_signals = self._check_topic_shifts(query)
        query_length_signal = self._analyze_query_length(query)
        conversation_depth_signal = self._analyze_conversation_depth(conversation_history)
        
        # Analyze recent context
        recent_context_signal = self._analyze_recent_context(query, conversation_history)
        
        # Apply weights and combine signals
        self._apply_temporal_signals(context_scores, temporal_signals)
        self._apply_continuation_signals(context_scores, continuation_signals)
        self._apply_topic_shift_signals(context_scores, topic_shift_signals)
        self._apply_query_length_signal(context_scores, query_length_signal)
        self._apply_conversation_depth_signal(context_scores, conversation_depth_signal)
        self._apply_recent_context_signal(context_scores, recent_context_signal)
        
        # Normalize scores
        total = sum(context_scores.values())
        if total > 0:
            for query_type in context_scores:
                context_scores[query_type] /= total
        
        logger.debug(f"Context analysis for query '{query}': {context_scores}")
        return context_scores
    
    def _check_temporal_references(self, query: str) -> float:
        """Check for temporal references in the query."""
        query_lower = query.lower()
        count = sum(1 for ref in self.context_indicators['temporal_references'] 
                   if ref in query_lower)
        # Increase base score for temporal references
        base_score = count * 0.4  # Doubled from 0.2
        
        # Additional boost for explicit history recall phrases
        history_phrases = ['what did we discuss', 'what was my question', 'earlier conversation']
        if any(phrase in query_lower for phrase in history_phrases):
            base_score += 0.3
            
        return min(base_score, 1.0)  # Cap at 1.0
    
    def _check_continuation_markers(self, query: str) -> float:
        """Check for continuation markers in the query."""
        query_lower = query.lower()
        count = sum(1 for marker in self.context_indicators['continuation_markers'] 
                   if marker in query_lower)
        return min(count * 0.25, 1.0)
    
    def _check_topic_shifts(self, query: str) -> float:
        """Check for topic shift markers in the query."""
        query_lower = query.lower()
        count = sum(1 for marker in self.context_indicators['topic_shift_markers'] 
                   if marker in query_lower)
        return min(count * 0.3, 1.0)
    
    def _analyze_query_length(self, query: str) -> float:
        """Analyze query length for context signals."""
        words = query.split()
        if not words:  # Empty query
            return 0.0
        
        if len(words) <= self.short_query_threshold:
            # Check for common short follow-up phrases
            short_followups = ['why', 'how', 'what', 'and', 'but', 'so']
            if any(word.lower() in short_followups for word in words):
                return 0.9  # Very likely a follow-up
            return 0.7  # Still likely a follow-up, but less certain
        return 0.2
    
    def _analyze_conversation_depth(self, history: List[Dict]) -> float:
        """Analyze conversation depth for context signals."""
        turns = len(history) // 2  # Each turn is a user message + assistant response
        if turns >= self.deep_conversation_threshold:
            return 0.7  # Deeper conversations more likely to have follow-ups
        return 0.3
    
    def _analyze_recent_context(
        self,
        query: str,
        history: List[Dict]
    ) -> Dict[str, float]:
        """Analyze recent conversation context."""
        if not history:
            return {'relevance': 0.0, 'type_hint': None}
        
        # Get the last few messages
        recent_messages = history[-4:]  # Last 2 turns
        
        # Look for references to previous content
        query_lower = query.lower()
        last_response = next((msg['content'] for msg in reversed(recent_messages) 
                            if msg['role'] == 'assistant'), '')
        
        # Check for references to numbered items or lists
        has_numbered_items = any(char.isdigit() for char in last_response)
        references_numbers = any(char.isdigit() for char in query_lower)
        
        if has_numbered_items and references_numbers:
            return {'relevance': 0.9, 'type_hint': 'CONTEXTUAL_FOLLOW_UP'}
        
        # Check for demonstrative references
        demonstratives = ['this', 'that', 'these', 'those']
        if any(dem in query_lower for dem in demonstratives):
            return {'relevance': 0.8, 'type_hint': 'CONTEXTUAL_FOLLOW_UP'}
        
        return {'relevance': 0.2, 'type_hint': None}
    
    def _apply_temporal_signals(
        self,
        scores: Dict[str, float],
        signal: float
    ) -> None:
        """Apply temporal reference signals to scores."""
        if signal > 0:
            scores['HISTORY_RECALL'] += signal * self.weights['temporal_reference']
    
    def _apply_continuation_signals(
        self,
        scores: Dict[str, float],
        signal: float
    ) -> None:
        """Apply continuation marker signals to scores."""
        if signal > 0:
            scores['CONTEXTUAL_FOLLOW_UP'] += signal * self.weights['continuation_marker']
    
    def _apply_topic_shift_signals(
        self,
        scores: Dict[str, float],
        signal: float
    ) -> None:
        """Apply topic shift signals to scores."""
        if signal > 0:
            scores['NEW_TOPIC_INFORMATIONAL'] += signal * self.weights['topic_shift']
    
    def _apply_query_length_signal(
        self,
        scores: Dict[str, float],
        signal: float
    ) -> None:
        """Apply query length signals to scores."""
        if signal > 0.5:  # Short query
            scores['CONTEXTUAL_FOLLOW_UP'] += signal * self.weights['query_length']
        else:  # Longer query
            scores['NEW_TOPIC_INFORMATIONAL'] += (1 - signal) * self.weights['query_length']
    
    def _apply_conversation_depth_signal(
        self,
        scores: Dict[str, float],
        signal: float
    ) -> None:
        """Apply conversation depth signals to scores."""
        if signal > 0.5:  # Deep conversation
            scores['CONTEXTUAL_FOLLOW_UP'] += signal * self.weights['conversation_depth']
            scores['HISTORY_RECALL'] += signal * (self.weights['conversation_depth'] * 0.5)
    
    def _apply_recent_context_signal(
        self,
        scores: Dict[str, float],
        signal: Dict[str, float]
    ) -> None:
        """Apply recent context signals to scores."""
        relevance = signal['relevance']
        type_hint = signal['type_hint']
        
        if type_hint == 'CONTEXTUAL_FOLLOW_UP':
            scores['CONTEXTUAL_FOLLOW_UP'] += relevance * 0.4
        elif relevance > 0.5:
            scores['CONTEXTUAL_FOLLOW_UP'] += relevance * 0.2
    
    def get_context_explanation(
        self,
        query: str,
        conversation_history: Optional[List[Dict]] = None
    ) -> List[str]:
        """
        Get a human-readable explanation of the context analysis.
        
        Args:
            query: The user's query
            conversation_history: Optional conversation history
            
        Returns:
            List of explanation strings
        """
        explanation = [f"Context analysis for query: '{query}'"]
        
        # Add basic signal explanations
        temporal_signal = self._check_temporal_references(query)
        if temporal_signal > 0:
            explanation.append(f"✓ Found temporal references (strength: {temporal_signal:.2f})")
        
        continuation_signal = self._check_continuation_markers(query)
        if continuation_signal > 0:
            explanation.append(f"✓ Found continuation markers (strength: {continuation_signal:.2f})")
        
        topic_shift_signal = self._check_topic_shifts(query)
        if topic_shift_signal > 0:
            explanation.append(f"✓ Found topic shift markers (strength: {topic_shift_signal:.2f})")
        
        # Add query length analysis
        words = len(query.split())
        explanation.append(f"Query length: {words} words "
                         f"({'short' if words <= self.short_query_threshold else 'normal'})")
        
        # Add conversation depth analysis if history available
        if conversation_history:
            turns = len(conversation_history) // 2
            explanation.append(f"Conversation depth: {turns} turns "
                            f"({'deep' if turns >= self.deep_conversation_threshold else 'shallow'})")
        
        return explanation
