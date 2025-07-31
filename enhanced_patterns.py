"""
Enhanced pattern libraries for intelligent RAG routing.
"""
from typing import Dict, List

# Pattern libraries for different query types
ENHANCED_PATTERNS: Dict[str, Dict[str, List[str]]] = {
    'NEW_TOPIC_PROCEDURAL': {
        'strong_indicators': [
            r'^how to\b',
            r'^how (do|can|would|should) (i|we|you) (?!.*(it|this|that|them)\b)',
            r'^what (are|is) the steps\b',
            r'^(guide|walk) me through\b',
            r'^show me how to\b',
            r'step[- ]by[- ]step'
        ],
        'weak_indicators': [
            r'\b(create|setup|configure|install)\b',
            r'\b(add|remove|delete|modify)\b',
            r'\b(guide|tutorial|walkthrough)\b'
        ]
    },
    'NEW_TOPIC_INFORMATIONAL': {
        'strong_indicators': [
            r'^what (is|are)\b(?!.*(how|steps))',
            r'^tell me about\b(?!.*(how|steps))',
            r'^why (do|does|is|are)\b',
            r'^when was\b',
            r'^who (is|are|created|made)\b',
            r'^explain\b(?!.*(how|steps))'
        ],
        'weak_indicators': [
            r'\b(mean|meaning|definition)\b',
            r'\b(explain|describe|define)\b(?!.*(how|steps))',
            r'\binformation (on|about)\b'
        ]
    },
    'CONTEXTUAL_FOLLOW_UP': {
        'strong_indicators': [
            r'^(tell|explain) me more\b',
            r'^elaborate\b',
            r'^what (else|more)\b',
            r'^(that|this|it)\b',
            r'^why\b(?!.*(is|are|do|does))',
            # FIXED: Allow "how do/can/would/should" when followed by pronouns or contextual references
            r'^how\b(?!.*(to|do|can|would|should))',
            r'^how (do|can|would|should) (i|we|you) (use|access|get|find) (it|this|that|them)\b',
            r'^how (do|can|would|should) (i|we|you) .*(it|this|that|them)\b',
            # NEW: Common follow-up phrases
            r'^(then what|what next|after that)\b',
            r'^(go on|continue|keep going)\b',
            r'^(what about|how about)\b',
            r'^(can you|could you) (tell|explain|show) me more\b',
            r'^(any|anything) (else|more)\b',
            r'^(the|that) (first|second|third|last|next) (one|item|point|step)\b'
        ],
        'weak_indicators': [
            r'\b(that|this|it)\b',
            r'\bmore details\b',
            r'\bcontinue\b',
            r'\band\b',
            # NEW: Additional weak indicators
            r'\b(further|additional|extra)\b',
            r'\b(other|another)\b',
            r'\b(specifically|particularly)\b',
            r'\b(example|instance)\b'
        ]
    },
    'HISTORY_RECALL': {
        'strong_indicators': [
            r'^what (was|did) (i|we)\b',
            r'^what was my (first|previous|last)\b',
            r'^(summarize|recap)\b',
            r'previous (question|topic)',
            r'earlier (question|topic)',
            # NEW: Additional history recall patterns
            r'^what did (i|we) (ask|say|discuss|talk about)\b',
            r'^(remind me|what was) (my|our|the) (question|topic)\b',
            r'^(go back to|return to|back to)\b',
            r'^(earlier|before) (i|we) (asked|mentioned|said)\b'
        ],
        'weak_indicators': [
            r'\b(earlier|before|previously)\b',
            r'\b(history|conversation|discussion)\b',
            r'\b(first|last|previous)\b'
        ]
    }
}

# Confidence boosters for ambiguous cases
CONFIDENCE_BOOSTERS = {
    'short_query_with_history': 0.3,  # "why?" with conversation history
    'demonstrative_reference': 0.4,   # "this", "that", "these", "those"
    'temporal_reference': 0.2,        # "earlier", "before", "previously"
    'numbered_reference': 0.5,        # "the first one", "number 2"
    'continuation_word': 0.3          # "also", "additionally", "furthermore"
}

# Pattern metadata
PATTERN_METADATA = {
    'HISTORY_RECALL': {
        'requires_history': True,
        'strong_confidence': 0.9,
        'weak_confidence': 0.6
    },
    'CONTEXTUAL_FOLLOW_UP': {
        'requires_history': True,
        'strong_confidence': 0.85,
        'weak_confidence': 0.5
    },
    'NEW_TOPIC_PROCEDURAL': {
        'requires_history': False,
        'strong_confidence': 0.9,
        'weak_confidence': 0.7
    },
    'NEW_TOPIC_INFORMATIONAL': {
        'requires_history': False,
        'strong_confidence': 0.9,
        'weak_confidence': 0.7
    }
}

# Context indicators
CONTEXT_INDICATORS = {
    'temporal_references': [
        'earlier',
        'before',
        'previously',
        'last time',
        'first',
        'initial',
        'original'
    ],
    'continuation_markers': [
        'also',
        'additionally',
        'furthermore',
        'moreover',
        'in addition',
        'another',
        'next',
        'then'
    ],
    'topic_shift_markers': [
        'however',
        'but',
        'instead',
        'rather',
        'on the other hand',
        'switching to',
        'moving to',
        'changing topics',
        'speaking of',
        'by the way'
    ]
}

def get_pattern_metadata(query_type: str) -> Dict:
    """Get metadata for a specific query type."""
    return PATTERN_METADATA.get(query_type, {
        'requires_history': False,
        'strong_confidence': 0.8,
        'weak_confidence': 0.5
    })

def get_context_indicators() -> Dict[str, List[str]]:
    """Get all context indicators."""
    return CONTEXT_INDICATORS

def get_patterns_by_type(query_type: str) -> Dict[str, List[str]]:
    """Get patterns for a specific query type."""
    return ENHANCED_PATTERNS.get(query_type, {
        'strong_indicators': [],
        'weak_indicators': []
    })
