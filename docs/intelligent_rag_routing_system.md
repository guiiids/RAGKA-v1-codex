# Intelligent RAG Routing System Documentation

## Overview

The Intelligent RAG Routing System is a conversational AI enhancement that determines when to search the knowledge base versus when to use existing conversation context. This prevents unnecessary searches for follow-up questions while ensuring new topics trigger appropriate knowledge retrieval.

## Problem Statement

**Original Issue**: The RAG system was performing knowledge base searches for every query, including follow-up questions that could be answered using existing conversation context. This resulted in:
- Inefficient resource usage
- Slower response times
- Potential context confusion
- Failed test cases expecting intelligent routing

## System Architecture

### Query Classification Pipeline

```
User Query → Query Type Detection → Routing Decision → Response Generation
     ↓              ↓                    ↓               ↓
"Tell me more" → CONTEXTUAL_FOLLOW_UP → Skip Search → Use History
"What is X?" → NEW_TOPIC_INFORMATIONAL → Perform Search → Fresh Context
```

### Query Types

1. **NEW_TOPIC_PROCEDURAL**
   - How-to questions requiring step-by-step instructions
   - Triggers: Knowledge base search + procedural system prompt
   - Examples: "How to create a calendar?", "Steps to configure X"

2. **NEW_TOPIC_INFORMATIONAL** 
   - General information requests about new topics
   - Triggers: Knowledge base search + default system prompt
   - Examples: "What is feature X?", "Tell me about Y"

3. **CONTEXTUAL_FOLLOW_UP**
   - Questions that reference previous conversation content
   - Triggers: Use existing context + conversation history
   - Examples: "Tell me more about that", "Elaborate on the first one"

4. **HISTORY_RECALL**
   - Questions about the conversation itself
   - Triggers: Use conversation history only
   - Examples: "What was my first question?", "What did we discuss?"

## Current Implementation (Phase 1)

### Detection Logic

The system uses a hierarchical pattern-matching approach:

```python
def detect_query_type(self, query: str, conversation_history: List[Dict] = None) -> str:
    # 1. History recall patterns (highest priority)
    # 2. Contextual follow-up patterns
    # 3. Short query analysis with context
    # 4. Conversation history analysis
    # 5. Procedural vs informational classification
```

### Pattern Categories

**History Recall Patterns:**
```regex
r'what (was|did) (i|we) (ask|say)'
r'what was my (first|previous|last|earlier) question'
r'(summarize|recap) (our|the) (conversation|discussion)'
```

**Follow-up Patterns:**
```regex
r'tell me more about (that|it|item|point|number|the (first|last|next|previous) one)'
r'elaborate on (that|it|this|those|these)'
r'(explain|clarify) (that|this|it) (further|more|again)'
```

**Procedural Patterns:**
```regex
r'how (to|do|can|would|should) (i|we|you|one)?\s'
r'what (is|are) the (steps|procedure|process)'
r'(guide|instructions|tutorial|walkthrough) (for|on|to)'
```

### Routing Implementation

```python
# Step 1: Classify query intent
query_type = self.detect_query_type(query, history)

# Step 2: Route based on classification
if query_type in ["NEW_TOPIC_PROCEDURAL", "NEW_TOPIC_INFORMATIONAL"]:
    # Perform knowledge base search
    kb_results = self.search_knowledge_base(query)
    context, src_map = self._prepare_context(kb_results)
    self._cumulative_src_map.update(src_map)
    
elif query_type in ["CONTEXTUAL_FOLLOW_UP", "HISTORY_RECALL"]:
    # Use existing context and conversation history
    src_map = self._cumulative_src_map
    context = "[No new context provided. Answer based on conversation history.]"
```

## Testing Framework

### Test Scenarios

1. **Standard Follow-up Test**
   - Initial query: "What is feature 1?" (triggers search)
   - Follow-up: "Tell me more about the first one." (skips search)
   - New topic: "What about CrossLab?" (triggers search)

2. **Varied Follow-up Test**
   - Initial query: "What is feature 1?" (triggers search)
   - Follow-up: "Elaborate on that." (skips search)

3. **History Recall Test**
   - Initial query: "What is feature 1?" (triggers search)
   - History query: "What was my first question?" (skips search)

### Success Metrics

- ✅ Search called exactly once for initial queries
- ✅ Search skipped for follow-up questions
- ✅ Search triggered for genuinely new topics
- ✅ Context continuity maintained across conversation

## Phase 2: Advanced ML-Based Routing (Proposed)

### Limitations of Current Regex-Based Approach

1. **Brittleness**: Patterns may not cover all linguistic variations
2. **Language Dependency**: Regex patterns are language-specific
3. **Context Insensitivity**: Limited understanding of semantic relationships
4. **Maintenance Overhead**: Requires manual pattern updates
5. **False Positives/Negatives**: Edge cases not covered by patterns

### Proposed ML-Based Solution

#### Architecture Overview

```
User Query + Conversation History → Feature Extraction → ML Classifier → Routing Decision
                                        ↓                    ↓              ↓
                                   Embeddings +         Intent         Search/NoSearch
                                   Context Features   Classification    + Context Type
```

#### Feature Engineering

**1. Semantic Embeddings**
```python
class SemanticFeatureExtractor:
    def extract_features(self, query: str, history: List[Dict]) -> Dict:
        return {
            'query_embedding': self.get_embedding(query),
            'last_response_embedding': self.get_embedding(history[-1]['content']),
            'semantic_similarity': self.cosine_similarity(query_emb, last_response_emb),
            'query_length': len(query.split()),
            'contains_pronouns': self.detect_pronouns(query),
            'temporal_references': self.detect_temporal_refs(query),
            'question_type': self.classify_question_type(query)
        }
```

**2. Conversational Context Features**
```python
def extract_context_features(self, history: List[Dict]) -> Dict:
    return {
        'conversation_length': len(history),
        'last_response_had_citations': self.has_citations(history[-1]),
        'topic_continuity_score': self.calculate_topic_continuity(history),
        'time_since_last_search': self.get_time_since_search(),
        'cumulative_sources_count': len(self._cumulative_src_map)
    }
```

#### ML Model Architecture

**Option 1: Lightweight Classification Model**
```python
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer

class IntentClassifier:
    def __init__(self):
        self.classifier = RandomForestClassifier(n_estimators=100)
        self.vectorizer = TfidfVectorizer(max_features=1000)
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    
    def predict_intent(self, query: str, context_features: Dict) -> str:
        # Combine text features with context features
        features = self.combine_features(query, context_features)
        return self.classifier.predict([features])[0]
```

**Option 2: Fine-tuned Language Model**
```python
from transformers import AutoTokenizer, AutoModelForSequenceClassification

class LLMIntentClassifier:
    def __init__(self):
        self.tokenizer = AutoTokenizer.from_pretrained('microsoft/DialoGPT-medium')
        self.model = AutoModelForSequenceClassification.from_pretrained(
            'microsoft/DialoGPT-medium', 
            num_labels=4  # 4 intent classes
        )
    
    def classify_intent(self, query: str, conversation_context: str) -> str:
        # Format input for the model
        input_text = f"Context: {conversation_context}\nQuery: {query}"
        inputs = self.tokenizer(input_text, return_tensors="pt", truncation=True)
        
        # Get prediction
        outputs = self.model(**inputs)
        predicted_class = torch.argmax(outputs.logits, dim=-1)
        return self.id_to_label[predicted_class.item()]
```

#### Training Data Generation

**Synthetic Data Generation**
```python
class TrainingDataGenerator:
    def generate_conversation_scenarios(self) -> List[Dict]:
        scenarios = []
        
        # Generate follow-up scenarios
        for topic in self.topics:
            initial_q = f"What is {topic}?"
            follow_ups = [
                f"Tell me more about {topic}",
                f"How does {topic} work?",
                f"What are the benefits of {topic}?",
                "Can you elaborate on that?",
                "What else should I know?"
            ]
            
            for follow_up in follow_ups:
                scenarios.append({
                    'conversation': [
                        {'role': 'user', 'content': initial_q},
                        {'role': 'assistant', 'content': f'{topic} is...'},
                        {'role': 'user', 'content': follow_up}
                    ],
                    'label': 'CONTEXTUAL_FOLLOW_UP'
                })
        
        return scenarios
```

**Real Conversation Mining**
```python
class ConversationMiner:
    def extract_patterns_from_logs(self, conversation_logs: List[Dict]) -> List[Dict]:
        """Extract training examples from real conversation logs"""
        training_data = []
        
        for conversation in conversation_logs:
            for i, turn in enumerate(conversation[2:], 2):  # Skip system message
                if turn['role'] == 'user':
                    context = conversation[:i]
                    label = self.human_annotate_or_heuristic_label(turn, context)
                    
                    training_data.append({
                        'query': turn['content'],
                        'context': context,
                        'label': label
                    })
        
        return training_data
```

#### Implementation Roadmap

**Phase 2.1: Data Collection & Model Training**
1. Collect conversation logs from existing system
2. Generate synthetic training data
3. Human annotation of edge cases
4. Train initial ML classifier
5. A/B test against regex system

**Phase 2.2: Advanced Features**
1. Multi-language support
2. Domain-specific fine-tuning
3. Confidence scoring and fallback mechanisms
4. Real-time model updates

**Phase 2.3: Production Optimization**
1. Model compression for faster inference
2. Caching and optimization
3. Monitoring and drift detection
4. Automated retraining pipeline

#### Evaluation Framework

**Metrics**
```python
class RoutingEvaluator:
    def evaluate_model(self, test_data: List[Dict]) -> Dict:
        return {
            'accuracy': self.calculate_accuracy(),
            'precision_per_class': self.calculate_precision(),
            'recall_per_class': self.calculate_recall(),
            'f1_score': self.calculate_f1(),
            'confusion_matrix': self.generate_confusion_matrix(),
            'search_efficiency': self.calculate_search_reduction(),
            'response_quality': self.evaluate_response_quality()
        }
```

**A/B Testing Framework**
```python
class ABTestFramework:
    def run_comparison(self, regex_router, ml_router, test_conversations):
        results = {
            'regex_performance': self.evaluate_router(regex_router, test_conversations),
            'ml_performance': self.evaluate_router(ml_router, test_conversations),
            'statistical_significance': self.calculate_significance()
        }
        return results
```

## Migration Strategy

### Phase 1 → Phase 2 Transition

1. **Parallel Implementation**: Run both systems simultaneously
2. **Gradual Rollout**: Start with low-risk conversations
3. **Fallback Mechanism**: Regex as backup for ML failures
4. **Performance Monitoring**: Track accuracy and response quality
5. **User Feedback Integration**: Collect user satisfaction data

### Risk Mitigation

1. **Model Confidence Thresholds**: Fall back to regex for low-confidence predictions
2. **Human-in-the-Loop**: Flag uncertain cases for human review
3. **Continuous Learning**: Update model based on production feedback
4. **Rollback Plan**: Quick reversion to regex system if needed

## Conclusion

The current regex-based system provides a solid foundation for intelligent RAG routing. The proposed ML-based Phase 2 will address scalability and robustness concerns while maintaining the core functionality that users depend on.

The key success factors for Phase 2 will be:
- Comprehensive training data collection
- Robust evaluation framework
- Careful migration strategy
- Continuous monitoring and improvement

This evolution will enable the system to handle more complex conversational patterns and provide better user experiences across diverse use cases.
