# Phase 2 Implementation Plan: ML-Based RAG Routing

## Executive Summary

This document outlines the practical implementation of an ML-based intelligent routing system to replace the current regex-based approach. The plan includes concrete code examples, timelines, and migration strategies.

## Current State Analysis

### Regex System Strengths
- ✅ Fast inference (< 1ms)
- ✅ Deterministic behavior
- ✅ No external dependencies
- ✅ Easy to debug and modify

### Regex System Limitations
- ❌ Limited pattern coverage
- ❌ Language-specific rules
- ❌ No semantic understanding
- ❌ Maintenance overhead
- ❌ Edge case handling

## Phase 2 Architecture

### Option A: Lightweight ML Classifier (Recommended)

**Advantages:**
- Fast inference (5-10ms)
- Lower resource requirements
- Easier to deploy and maintain
- Good interpretability

**Implementation:**

```python
# ml_intent_classifier.py
import numpy as np
import pickle
from typing import Dict, List, Tuple
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sentence_transformers import SentenceTransformer
import spacy

class MLIntentClassifier:
    def __init__(self, model_path: str = None):
        self.model = None
        self.vectorizer = None
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.nlp = spacy.load('en_core_web_sm')
        
        # Intent mapping
        self.intent_labels = {
            0: "NEW_TOPIC_INFORMATIONAL",
            1: "NEW_TOPIC_PROCEDURAL", 
            2: "CONTEXTUAL_FOLLOW_UP",
            3: "HISTORY_RECALL"
        }
        
        if model_path:
            self.load_model(model_path)
    
    def extract_linguistic_features(self, query: str) -> Dict:
        """Extract linguistic features from the query"""
        doc = self.nlp(query)
        
        features = {
            # Basic features
            'query_length': len(query.split()),
            'char_length': len(query),
            'question_mark_count': query.count('?'),
            
            # Linguistic features
            'has_pronouns': any(token.pos_ == 'PRON' for token in doc),
            'pronoun_count': sum(1 for token in doc if token.pos_ == 'PRON'),
            'has_demonstratives': any(token.text.lower() in ['this', 'that', 'these', 'those'] for token in doc),
            'has_temporal_refs': any(token.text.lower() in ['first', 'last', 'previous', 'earlier', 'before'] for token in doc),
            
            # Question type features
            'starts_with_wh': query.lower().startswith(('what', 'how', 'why', 'when', 'where', 'who')),
            'starts_with_how': query.lower().startswith('how'),
            'contains_steps': 'step' in query.lower(),
            'contains_more': 'more' in query.lower(),
            'contains_elaborate': 'elaborate' in query.lower(),
            
            # Procedural indicators
            'has_procedural_words': any(word in query.lower() for word in [
                'how to', 'steps', 'procedure', 'guide', 'tutorial', 'instructions',
                'create', 'setup', 'configure', 'install', 'build'
            ]),
            
            # Follow-up indicators
            'has_followup_words': any(word in query.lower() for word in [
                'tell me more', 'elaborate', 'explain further', 'continue',
                'what else', 'anything else', 'more details'
            ]),
            
            # History recall indicators
            'has_history_words': any(word in query.lower() for word in [
                'what did', 'what was', 'my question', 'we discussed', 'earlier',
                'before', 'previous', 'first question'
            ])
        }
        
        return features
    
    def extract_context_features(self, conversation_history: List[Dict]) -> Dict:
        """Extract features from conversation context"""
        if not conversation_history or len(conversation_history) < 2:
            return {
                'conversation_length': 0,
                'has_previous_response': False,
                'last_response_length': 0,
                'has_citations': False,
                'turns_since_search': 0
            }
        
        # Get last assistant response
        last_assistant_msg = None
        for msg in reversed(conversation_history):
            if msg.get('role') == 'assistant':
                last_assistant_msg = msg
                break
        
        features = {
            'conversation_length': len(conversation_history),
            'has_previous_response': last_assistant_msg is not None,
            'last_response_length': len(last_assistant_msg.get('content', '').split()) if last_assistant_msg else 0,
            'has_citations': '[' in last_assistant_msg.get('content', '') if last_assistant_msg else False,
            'turns_since_search': self._calculate_turns_since_search(conversation_history)
        }
        
        return features
    
    def _calculate_turns_since_search(self, history: List[Dict]) -> int:
        """Calculate turns since last search was performed"""
        # This would need to be tracked in the conversation metadata
        # For now, return a placeholder
        return min(len(history) // 2, 5)  # Approximate based on conversation length
    
    def extract_semantic_features(self, query: str, conversation_history: List[Dict]) -> Dict:
        """Extract semantic similarity features"""
        query_embedding = self.embedding_model.encode([query])[0]
        
        if not conversation_history:
            return {
                'semantic_similarity_to_last': 0.0,
                'max_similarity_to_history': 0.0,
                'avg_similarity_to_history': 0.0
            }
        
        # Get embeddings for recent conversation
        recent_texts = []
        for msg in conversation_history[-4:]:  # Last 4 messages
            if msg.get('role') in ['user', 'assistant']:
                recent_texts.append(msg.get('content', ''))
        
        if not recent_texts:
            return {
                'semantic_similarity_to_last': 0.0,
                'max_similarity_to_history': 0.0,
                'avg_similarity_to_history': 0.0
            }
        
        history_embeddings = self.embedding_model.encode(recent_texts)
        similarities = [np.dot(query_embedding, hist_emb) / 
                       (np.linalg.norm(query_embedding) * np.linalg.norm(hist_emb))
                       for hist_emb in history_embeddings]
        
        return {
            'semantic_similarity_to_last': similarities[-1] if similarities else 0.0,
            'max_similarity_to_history': max(similarities) if similarities else 0.0,
            'avg_similarity_to_history': np.mean(similarities) if similarities else 0.0
        }
    
    def combine_features(self, query: str, conversation_history: List[Dict]) -> np.ndarray:
        """Combine all features into a single feature vector"""
        linguistic_features = self.extract_linguistic_features(query)
        context_features = self.extract_context_features(conversation_history)
        semantic_features = self.extract_semantic_features(query, conversation_history)
        
        # Combine all features
        all_features = {**linguistic_features, **context_features, **semantic_features}
        
        # Convert to ordered array (ensure consistent ordering)
        feature_names = sorted(all_features.keys())
        feature_vector = np.array([all_features[name] for name in feature_names])
        
        return feature_vector
    
    def predict_intent(self, query: str, conversation_history: List[Dict] = None) -> Tuple[str, float]:
        """Predict intent with confidence score"""
        if not self.model:
            raise ValueError("Model not loaded. Call load_model() or train_model() first.")
        
        features = self.combine_features(query, conversation_history or [])
        
        # Get prediction and confidence
        prediction = self.model.predict([features])[0]
        probabilities = self.model.predict_proba([features])[0]
        confidence = max(probabilities)
        
        intent = self.intent_labels[prediction]
        return intent, confidence
    
    def train_model(self, training_data: List[Dict]):
        """Train the ML model"""
        X = []
        y = []
        
        for example in training_data:
            features = self.combine_features(
                example['query'], 
                example.get('conversation_history', [])
            )
            X.append(features)
            y.append(example['label_id'])  # 0, 1, 2, or 3
        
        X = np.array(X)
        y = np.array(y)
        
        # Train Random Forest
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42,
            class_weight='balanced'
        )
        self.model.fit(X, y)
        
        return self.model
    
    def save_model(self, path: str):
        """Save the trained model"""
        model_data = {
            'model': self.model,
            'intent_labels': self.intent_labels
        }
        with open(path, 'wb') as f:
            pickle.dump(model_data, f)
    
    def load_model(self, path: str):
        """Load a trained model"""
        with open(path, 'rb') as f:
            model_data = pickle.load(f)
        
        self.model = model_data['model']
        self.intent_labels = model_data['intent_labels']
```

### Training Data Generation

```python
# training_data_generator.py
import random
from typing import List, Dict

class TrainingDataGenerator:
    def __init__(self):
        self.topics = [
            "calendar", "user management", "permissions", "API integration",
            "dashboard", "reports", "notifications", "settings", "backup",
            "security", "authentication", "workflows", "templates"
        ]
        
        self.procedural_templates = [
            "How to {action} {topic}?",
            "What are the steps to {action} {topic}?",
            "Can you guide me through {action} {topic}?",
            "I need to {action} {topic}, what's the process?",
            "Steps for {action} {topic}",
            "Tutorial for {action} {topic}",
            "Instructions to {action} {topic}"
        ]
        
        self.informational_templates = [
            "What is {topic}?",
            "Tell me about {topic}",
            "Explain {topic}",
            "What are the features of {topic}?",
            "How does {topic} work?",
            "What are the benefits of {topic}?",
            "When should I use {topic}?"
        ]
        
        self.followup_templates = [
            "Tell me more about that",
            "Can you elaborate?",
            "What else should I know?",
            "More details please",
            "Explain further",
            "Continue",
            "What about the first one?",
            "Tell me more about the last point",
            "How does that work?",
            "Why is that important?"
        ]
        
        self.history_templates = [
            "What was my first question?",
            "What did we discuss earlier?",
            "Can you summarize our conversation?",
            "What was my previous question?",
            "What did I ask before?",
            "Recap what we talked about"
        ]
        
        self.actions = [
            "create", "setup", "configure", "install", "delete", "modify",
            "update", "manage", "access", "share", "export", "import"
        ]
    
    def generate_training_data(self, num_examples: int = 1000) -> List[Dict]:
        """Generate synthetic training data"""
        training_data = []
        
        # Generate examples for each intent class
        examples_per_class = num_examples // 4
        
        # NEW_TOPIC_PROCEDURAL examples
        for _ in range(examples_per_class):
            topic = random.choice(self.topics)
            action = random.choice(self.actions)
            template = random.choice(self.procedural_templates)
            query = template.format(topic=topic, action=action)
            
            training_data.append({
                'query': query,
                'conversation_history': [],
                'label': 'NEW_TOPIC_PROCEDURAL',
                'label_id': 1
            })
        
        # NEW_TOPIC_INFORMATIONAL examples
        for _ in range(examples_per_class):
            topic = random.choice(self.topics)
            template = random.choice(self.informational_templates)
            query = template.format(topic=topic)
            
            training_data.append({
                'query': query,
                'conversation_history': [],
                'label': 'NEW_TOPIC_INFORMATIONAL',
                'label_id': 0
            })
        
        # CONTEXTUAL_FOLLOW_UP examples
        for _ in range(examples_per_class):
            # Create a conversation context
            topic = random.choice(self.topics)
            initial_query = f"What is {topic}?"
            initial_response = f"{topic} is a feature that allows you to..."
            
            followup_query = random.choice(self.followup_templates)
            
            conversation_history = [
                {'role': 'system', 'content': 'You are a helpful assistant.'},
                {'role': 'user', 'content': initial_query},
                {'role': 'assistant', 'content': initial_response}
            ]
            
            training_data.append({
                'query': followup_query,
                'conversation_history': conversation_history,
                'label': 'CONTEXTUAL_FOLLOW_UP',
                'label_id': 2
            })
        
        # HISTORY_RECALL examples
        for _ in range(examples_per_class):
            # Create a longer conversation context
            topic1 = random.choice(self.topics)
            topic2 = random.choice(self.topics)
            
            conversation_history = [
                {'role': 'system', 'content': 'You are a helpful assistant.'},
                {'role': 'user', 'content': f"How to setup {topic1}?"},
                {'role': 'assistant', 'content': f"To setup {topic1}, follow these steps..."},
                {'role': 'user', 'content': f"What about {topic2}?"},
                {'role': 'assistant', 'content': f"{topic2} works differently..."}
            ]
            
            history_query = random.choice(self.history_templates)
            
            training_data.append({
                'query': history_query,
                'conversation_history': conversation_history,
                'label': 'HISTORY_RECALL',
                'label_id': 3
            })
        
        # Shuffle the data
        random.shuffle(training_data)
        return training_data
    
    def generate_edge_cases(self) -> List[Dict]:
        """Generate edge case examples"""
        edge_cases = [
            # Ambiguous cases
            {
                'query': 'What about it?',
                'conversation_history': [
                    {'role': 'user', 'content': 'Tell me about calendars'},
                    {'role': 'assistant', 'content': 'Calendars help you schedule...'}
                ],
                'label': 'CONTEXTUAL_FOLLOW_UP',
                'label_id': 2
            },
            # Short procedural
            {
                'query': 'How?',
                'conversation_history': [
                    {'role': 'user', 'content': 'I need to create a calendar'},
                    {'role': 'assistant', 'content': 'You can create calendars in the system...'}
                ],
                'label': 'CONTEXTUAL_FOLLOW_UP',
                'label_id': 2
            },
            # Mixed intent
            {
                'query': 'How do I do what we discussed?',
                'conversation_history': [
                    {'role': 'user', 'content': 'What is user management?'},
                    {'role': 'assistant', 'content': 'User management allows you to...'}
                ],
                'label': 'CONTEXTUAL_FOLLOW_UP',
                'label_id': 2
            }
        ]
        
        return edge_cases
```

### Integration with Existing System

```python
# enhanced_rag_assistant.py
from typing import List, Dict, Tuple, Optional, Any
from ml_intent_classifier import MLIntentClassifier
import logging

class EnhancedRAGAssistant(FlaskRAGAssistantV2):
    """Enhanced RAG Assistant with ML-based routing"""
    
    def __init__(self, settings=None, use_ml_routing=True, ml_model_path=None):
        super().__init__(settings)
        
        self.use_ml_routing = use_ml_routing
        self.ml_classifier = None
        self.confidence_threshold = 0.7  # Fallback to regex if confidence < threshold
        
        if use_ml_routing:
            try:
                self.ml_classifier = MLIntentClassifier(ml_model_path)
                logger.info("ML classifier loaded successfully")
            except Exception as e:
                logger.warning(f"Failed to load ML classifier: {e}. Falling back to regex.")
                self.use_ml_routing = False
    
    def detect_query_type_ml(self, query: str, conversation_history: List[Dict] = None) -> Tuple[str, float]:
        """Detect query type using ML classifier"""
        if not self.ml_classifier:
            raise ValueError("ML classifier not loaded")
        
        return self.ml_classifier.predict_intent(query, conversation_history)
    
    def detect_query_type_hybrid(self, query: str, conversation_history: List[Dict] = None) -> str:
        """Hybrid approach: ML with regex fallback"""
        if not self.use_ml_routing or not self.ml_classifier:
            # Fallback to regex
            return super().detect_query_type(query, conversation_history)
        
        try:
            # Try ML classification first
            ml_intent, confidence = self.detect_query_type_ml(query, conversation_history)
            
            if confidence >= self.confidence_threshold:
                logger.info(f"ML classification: {ml_intent} (confidence: {confidence:.3f})")
                return ml_intent
            else:
                # Low confidence, fallback to regex
                regex_intent = super().detect_query_type(query, conversation_history)
                logger.info(f"Low ML confidence ({confidence:.3f}), using regex: {regex_intent}")
                return regex_intent
                
        except Exception as e:
            logger.error(f"ML classification failed: {e}. Using regex fallback.")
            return super().detect_query_type(query, conversation_history)
    
    def detect_query_type(self, query: str, conversation_history: List[Dict] = None) -> str:
        """Override to use hybrid approach"""
        return self.detect_query_type_hybrid(query, conversation_history)
```

## Implementation Timeline

### Phase 2.1: Foundation (Weeks 1-4)
- **Week 1**: Set up ML infrastructure and dependencies
- **Week 2**: Implement feature extraction and training data generation
- **Week 3**: Train initial model and basic evaluation
- **Week 4**: Integration with existing system (hybrid mode)

### Phase 2.2: Testing & Optimization (Weeks 5-8)
- **Week 5**: Comprehensive testing and edge case handling
- **Week 6**: Performance optimization and model tuning
- **Week 7**: A/B testing framework setup
- **Week 8**: Production deployment preparation

### Phase 2.3: Production Rollout (Weeks 9-12)
- **Week 9**: Gradual rollout to 10% of traffic
- **Week 10**: Monitor and adjust, expand to 50%
- **Week 11**: Full rollout with monitoring
- **Week 12**: Performance analysis and documentation

## Risk Mitigation

### Technical Risks
1. **Model Performance**: Continuous monitoring and retraining
2. **Latency Impact**: Caching and model optimization
3. **Memory Usage**: Efficient model loading and resource management
4. **Dependency Issues**: Containerization and version pinning

### Business Risks
1. **User Experience**: Gradual rollout with rollback capability
2. **Accuracy Regression**: A/B testing and quality metrics
3. **Maintenance Overhead**: Automated monitoring and alerting

## Success Metrics

### Technical Metrics
- **Accuracy**: >95% on test set
- **Latency**: <50ms additional overhead
- **Memory**: <500MB additional usage
- **Uptime**: 99.9% availability

### Business Metrics
- **Search Efficiency**: 30% reduction in unnecessary searches
- **User Satisfaction**: Maintain or improve current ratings
- **Response Quality**: No degradation in answer quality

## Conclusion

The ML-based Phase 2 implementation provides a robust, scalable solution for intelligent RAG routing while maintaining backward compatibility and minimizing risks through careful planning and gradual deployment.
