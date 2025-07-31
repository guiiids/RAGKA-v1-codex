"""
Logging framework for routing decisions to enable analysis and improvement.
"""
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RoutingDecisionLogger:
    """Logger for tracking and analyzing routing decisions."""
    
    def __init__(self, log_dir: str = "logs/routing"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Current log file path (rotated daily)
        self.current_log_file = self._get_current_log_path()
        
        # Initialize counters
        self.decision_counts = {
            'total': 0,
            'by_type': {},
            'by_confidence': {
                'high': 0,    # confidence >= 0.8
                'medium': 0,  # 0.6 <= confidence < 0.8
                'low': 0      # confidence < 0.6
            }
        }
        
        # NEW: Performance tracking for cache optimization
        self.performance_log = []
        self.cache_readiness_metrics = {
            'frequent_queries': {},      # Query -> count mapping
            'pattern_hit_rates': {},     # Pattern -> hit rate
            'gpt4_response_times': [],   # Response time tracking
            'context_analysis_times': [] # Context analysis timing
        }
    
    def _get_current_log_path(self) -> Path:
        """Get the current log file path based on date."""
        date_str = datetime.utcnow().strftime('%Y-%m-%d')
        return self.log_dir / f"routing_decisions_{date_str}.jsonl"
    
    def log_decision(
        self,
        query: str,
        detected_type: str,
        confidence: float,
        search_performed: bool,
        conversation_context: Optional[List[Dict]] = None,
        pattern_matches: Optional[Dict] = None,
        processing_time_ms: Optional[float] = None,
        mediator_used: bool = False
    ) -> None:
        """
        Log a routing decision with detailed information.
        
        Args:
            query: The user's query
            detected_type: The detected query type
            confidence: Confidence score for the classification
            search_performed: Whether a knowledge base search was performed
            conversation_context: Optional conversation history
            pattern_matches: Optional details about pattern matches
            processing_time_ms: Optional processing time in milliseconds
        """
        # Rotate log file if needed
        current_path = self._get_current_log_path()
        if current_path != self.current_log_file:
            self.current_log_file = current_path
        
        # Update counters
        self.decision_counts['total'] += 1
        self.decision_counts['by_type'][detected_type] = \
            self.decision_counts['by_type'].get(detected_type, 0) + 1
        
        # Update confidence counters
        if confidence >= 0.8:
            self.decision_counts['by_confidence']['high'] += 1
        elif confidence >= 0.6:
            self.decision_counts['by_confidence']['medium'] += 1
        else:
            self.decision_counts['by_confidence']['low'] += 1
        
        # Prepare log entry
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'query': query,
            'detected_type': detected_type,
            'confidence': confidence,
            'search_performed': search_performed,
            'conversation_length': len(conversation_context) if conversation_context else 0,
            'pattern_matches': pattern_matches,
            'processing_time_ms': processing_time_ms,
            'mediator_used': mediator_used
        }
        
        # Write to log file
        try:
            with open(self.current_log_file, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            logger.error(f"Failed to write to log file: {e}")
    
    def analyze_recent_decisions(self, hours: int = 24) -> Dict[str, Any]:
        """
        Analyze routing decisions from the past N hours.
        
        Args:
            hours: Number of hours to analyze
            
        Returns:
            Dictionary containing analysis results
        """
        cutoff_time = datetime.utcnow().timestamp() - (hours * 3600)
        
        analysis = {
            'total_decisions': 0,
            'type_distribution': {},
            'confidence_distribution': {
                'high': 0,
                'medium': 0,
                'low': 0
            },
            'search_percentage': 0,
            'avg_processing_time': 0.0,
            'mediator_usage': {
                'total_uses': 0,
                'success_rate': 0.0,
                'avg_confidence_before': 0.0,
                'avg_confidence_after': 0.0
            },
            'potential_issues': []
        }
        
        processing_times = []
        search_count = 0
        
        try:
            with open(self.current_log_file, 'r') as f:
                for line in f:
                    entry = json.loads(line.strip())
                    
                    # Skip entries outside time window
                    entry_time = datetime.fromisoformat(entry['timestamp']).timestamp()
                    if entry_time < cutoff_time:
                        continue
                    
                    # Update counters
                    analysis['total_decisions'] += 1
                    
                    # Update type distribution
                    query_type = entry['detected_type']
                    analysis['type_distribution'][query_type] = \
                        analysis['type_distribution'].get(query_type, 0) + 1
                    
                    # Update confidence distribution
                    confidence = entry['confidence']
                    if confidence >= 0.8:
                        analysis['confidence_distribution']['high'] += 1
                    elif confidence >= 0.6:
                        analysis['confidence_distribution']['medium'] += 1
                    else:
                        analysis['confidence_distribution']['low'] += 1
                    
                    # Track searches
                    if entry['search_performed']:
                        search_count += 1
                    
                    # Track processing time
                    if entry.get('processing_time_ms'):
                        processing_times.append(entry['processing_time_ms'])
                    
                    # Track mediator usage
                    if entry.get('mediator_used'):
                        analysis['mediator_usage']['total_uses'] += 1
                        
                        # If we have before/after confidence scores
                        if entry.get('confidence_before') and entry.get('confidence'):
                            analysis['mediator_usage']['avg_confidence_before'] += entry['confidence_before']
                            analysis['mediator_usage']['avg_confidence_after'] += entry['confidence']
                    
                    # Check for potential issues
                    self._check_for_issues(entry, analysis['potential_issues'])
        
        except FileNotFoundError:
            logger.warning(f"No log file found at {self.current_log_file}")
            return analysis
        
        # Calculate final statistics
        if analysis['total_decisions'] > 0:
            analysis['search_percentage'] = (search_count / analysis['total_decisions']) * 100
            
            if processing_times:
                analysis['avg_processing_time'] = sum(processing_times) / len(processing_times)
            
            # Calculate mediator statistics
            mediator_uses = analysis['mediator_usage']['total_uses']
            if mediator_uses > 0:
                analysis['mediator_usage']['success_rate'] = (
                    mediator_uses / analysis['total_decisions']
                ) * 100
                
                analysis['mediator_usage']['avg_confidence_before'] /= mediator_uses
                analysis['mediator_usage']['avg_confidence_after'] /= mediator_uses
        
        return analysis
    
    def _check_for_issues(self, entry: Dict, issues: List[Dict]) -> None:
        """Check a log entry for potential issues, including mediator-related concerns."""
        # Low confidence classification
        if entry['confidence'] < 0.6:
            issues.append({
                'type': 'low_confidence',
                'query': entry['query'],
                'confidence': entry['confidence'],
                'detected_type': entry['detected_type']
            })
        
        # Slow processing time
        processing_time = entry.get('processing_time_ms')
        if processing_time is not None and processing_time > 100:  # Over 100ms
            issues.append({
                'type': 'slow_processing',
                'query': entry['query'],
                'processing_time_ms': entry['processing_time_ms']
            })
        
        # Short query classified as new topic
        if (len(entry['query'].split()) <= 3 and 
            entry['detected_type'].startswith('NEW_TOPIC') and 
            entry['confidence'] < 0.8):
            issues.append({
                'type': 'short_query_new_topic',
                'query': entry['query'],
                'confidence': entry['confidence']
            })
        
        # Mediator-related issues
        if entry.get('mediator_used'):
            # Check if mediator significantly improved confidence
            confidence_before = entry.get('confidence_before', 0)
            confidence_after = entry.get('confidence', 0)
            
            if confidence_after <= confidence_before:
                issues.append({
                    'type': 'mediator_no_improvement',
                    'query': entry['query'],
                    'confidence_before': confidence_before,
                    'confidence_after': confidence_after
                })
            
            # Check for repeated mediator use on similar queries
            if entry.get('conversation_length', 0) > 0:
                issues.append({
                    'type': 'mediator_in_conversation',
                    'query': entry['query'],
                    'conversation_length': entry['conversation_length']
                })
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics for all logged decisions."""
        return {
            'total_decisions': self.decision_counts['total'],
            'by_type': self.decision_counts['by_type'],
            'by_confidence': self.decision_counts['by_confidence']
        }
    
    def clear_old_logs(self, days: int = 30) -> None:
        """Clear log files older than specified days."""
        cutoff_time = datetime.utcnow().timestamp() - (days * 24 * 3600)
        
        for log_file in self.log_dir.glob('routing_decisions_*.jsonl'):
            try:
                # Extract date from filename
                date_str = log_file.stem.split('_')[-1]
                log_date = datetime.strptime(date_str, '%Y-%m-%d')
                
                if log_date.timestamp() < cutoff_time:
                    log_file.unlink()
                    logger.info(f"Removed old log file: {log_file}")
            
            except (ValueError, OSError) as e:
                logger.error(f"Error processing log file {log_file}: {e}")
    
    def log_performance_metrics(
        self,
        query: str,
        classification_method: str,  # 'quick', 'regex', 'gpt4'
        response_time_ms: float,
        confidence: float,
        cache_key: Optional[str] = None
    ) -> None:
        """Log performance metrics for cache optimization."""
        
        import time
        timestamp = time.time()
        
        # Track frequent queries (future cache candidates)
        query_hash = hash(query.lower().strip())
        self.cache_readiness_metrics['frequent_queries'][query_hash] = \
            self.cache_readiness_metrics['frequent_queries'].get(query_hash, 0) + 1
        
        # Track method performance
        perf_entry = {
            'timestamp': timestamp,
            'query_hash': query_hash,
            'method': classification_method,
            'response_time_ms': response_time_ms,
            'confidence': confidence,
            'cache_key': cache_key
        }
        
        self.performance_log.append(perf_entry)
        
        # Keep only last 1000 entries
        if len(self.performance_log) > 1000:
            self.performance_log = self.performance_log[-1000:]
    
    def get_cache_optimization_report(self) -> Dict:
        """Generate report for Redis cache optimization."""
        
        # Find most frequent queries (cache candidates)
        frequent_queries = sorted(
            self.cache_readiness_metrics['frequent_queries'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:20]  # Top 20 most frequent
        
        # Calculate average response times by method
        method_times = {}
        for entry in self.performance_log:
            method = entry['method']
            if method not in method_times:
                method_times[method] = []
            method_times[method].append(entry['response_time_ms'])
        
        avg_times = {
            method: sum(times) / len(times) if times else 0
            for method, times in method_times.items()
        }
        
        return {
            'top_cache_candidates': frequent_queries,
            'average_response_times': avg_times,
            'total_queries_logged': len(self.performance_log),
            'cache_hit_potential': len(frequent_queries) / len(self.performance_log) if self.performance_log else 0
        }
