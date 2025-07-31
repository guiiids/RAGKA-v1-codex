"""
Enhanced pattern matching system with strong/weak indicator matching.
"""
from typing import Dict, List, Tuple, Optional
import re
import logging
from enhanced_patterns import (
    get_patterns_by_type,
    get_pattern_metadata,
    get_context_indicators,
    ENHANCED_PATTERNS
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnhancedPatternMatcher:
    """
    Enhanced pattern matching system that uses strong and weak indicators
    for more accurate query classification.
    """
    
    def __init__(self):
        # Cache for compiled regex patterns
        self._compiled_patterns: Dict[str, Dict[str, List[re.Pattern]]] = {}
        self._compile_patterns()
    
    def _compile_patterns(self) -> None:
        """Pre-compile regex patterns for better performance."""
        for query_type, patterns in ENHANCED_PATTERNS.items():
            self._compiled_patterns[query_type] = {
                'strong': [],
                'weak': []
            }
            
            # Compile strong indicators
            for pattern in patterns['strong_indicators']:
                try:
                    compiled = re.compile(pattern, re.IGNORECASE)
                    self._compiled_patterns[query_type]['strong'].append(compiled)
                except re.error as e:
                    logger.error(f"Invalid regex pattern '{pattern}': {e}")
            
            # Compile weak indicators
            for pattern in patterns['weak_indicators']:
                try:
                    compiled = re.compile(pattern, re.IGNORECASE)
                    self._compiled_patterns[query_type]['weak'].append(compiled)
                except re.error as e:
                    logger.error(f"Invalid regex pattern '{pattern}': {e}")
    
    def _check_patterns(
        self,
        query: str,
        query_type: str,
        pattern_type: str
    ) -> bool:
        """Check query against a specific type of patterns."""
        if query_type not in self._compiled_patterns:
            return False
        
        for pattern in self._compiled_patterns[query_type][pattern_type]:
            if pattern.search(query):
                return True
        
        return False
    
    def _get_initial_classification(
        self,
        query: str,
        conversation_history: Optional[List[Dict]] = None
    ) -> List[Tuple[str, float]]:
        """Get initial classification scores for all query types."""
        results = []
        
        for query_type in ENHANCED_PATTERNS.keys():
            metadata = get_pattern_metadata(query_type)
            
            # Skip if history is required but not provided
            if metadata['requires_history'] and not conversation_history:
                continue
            
            # Check strong indicators first
            if self._check_patterns(query, query_type, 'strong'):
                results.append((query_type, metadata['strong_confidence']))
                continue
            
            # Check weak indicators
            if self._check_patterns(query, query_type, 'weak'):
                results.append((query_type, metadata['weak_confidence']))
                continue
        
        return results
    
    def _analyze_context(
        self,
        query: str,
        conversation_history: Optional[List[Dict]] = None
    ) -> Dict[str, float]:
        """Analyze conversation context for additional signals."""
        context_scores = {
            'HISTORY_RECALL': 0.0,
            'CONTEXTUAL_FOLLOW_UP': 0.0,
            'NEW_TOPIC_PROCEDURAL': 0.0,
            'NEW_TOPIC_INFORMATIONAL': 0.0
        }
        
        if not conversation_history:
            return context_scores
        
        # Get context indicators
        indicators = get_context_indicators()
        query_lower = query.lower()
        
        # Check temporal references
        temporal_refs = sum(1 for ref in indicators['temporal_references'] 
                          if ref in query_lower)
        if temporal_refs > 0:
            context_scores['HISTORY_RECALL'] += 0.1 * temporal_refs
        
        # Check continuation markers
        continuation_marks = sum(1 for mark in indicators['continuation_markers'] 
                              if mark in query_lower)
        if continuation_marks > 0:
            context_scores['CONTEXTUAL_FOLLOW_UP'] += 0.1 * continuation_marks
        
        # Check topic shifts
        topic_shifts = sum(1 for mark in indicators['topic_shift_markers'] 
                         if mark in query_lower)
        if topic_shifts > 0:
            context_scores['NEW_TOPIC_INFORMATIONAL'] += 0.1 * topic_shifts
        
        # Analyze query length
        words = query.split()
        if len(words) <= 2 and conversation_history:
            context_scores['CONTEXTUAL_FOLLOW_UP'] += 0.2
        
        return context_scores
    
    def classify_query(
        self,
        query: str,
        conversation_history: Optional[List[Dict]] = None
    ) -> Tuple[str, float]:
        """
        Classify the query type using strong and weak indicators.
        
        Args:
            query: The user's query
            conversation_history: Optional list of previous conversation turns
            
        Returns:
            Tuple of (query_type, confidence_score)
        """
        query = query.strip()
        if not query:
            return 'NEW_TOPIC_INFORMATIONAL', 0.0
        
        # Get initial classification based on patterns
        initial_results = self._get_initial_classification(query, conversation_history)
        
        # If we have a strong match, use it
        strong_matches = [(t, c) for t, c in initial_results if c >= 0.8]
        if strong_matches:
            best_match = max(strong_matches, key=lambda x: x[1])
            logger.info(f"Query '{query}' classified as {best_match[0]} "
                       f"with confidence {best_match[1]:.2f}")
            return best_match
        
        # Get context scores
        context_scores = self._analyze_context(query, conversation_history)
        
        # Combine pattern matches with context scores
        final_scores = {}
        for query_type, base_confidence in initial_results:
            final_scores[query_type] = base_confidence + context_scores[query_type]
        
        # Add context-only scores for types without pattern matches
        for query_type, context_score in context_scores.items():
            if query_type not in final_scores and context_score > 0:
                final_scores[query_type] = context_score
        
        if not final_scores:
            # Default to informational with low confidence
            return 'NEW_TOPIC_INFORMATIONAL', 0.5
        
        # Get best match
        best_type = max(final_scores.items(), key=lambda x: x[1])
        
        logger.info(f"Query '{query}' classified as {best_type[0]} "
                   f"with confidence {best_type[1]:.2f}")
        
        return best_type[0], min(best_type[1], 1.0)
    
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
            A string explaining how the confidence was calculated
        """
        explanation = [f"Classification of query: '{query}'"]
        explanation.append(f"Detected type: {query_type}")
        explanation.append(f"Overall confidence: {confidence:.2f}")
        
        # Check strong indicators
        if self._check_patterns(query, query_type, 'strong'):
            explanation.append("✓ Matched strong indicator")
            metadata = get_pattern_metadata(query_type)
            explanation.append(f"  Strong match confidence: {metadata['strong_confidence']:.2f}")
        
        # Check weak indicators
        if self._check_patterns(query, query_type, 'weak'):
            explanation.append("✓ Matched weak indicator")
            metadata = get_pattern_metadata(query_type)
            explanation.append(f"  Weak match confidence: {metadata['weak_confidence']:.2f}")
        
        return "\n".join(explanation)
