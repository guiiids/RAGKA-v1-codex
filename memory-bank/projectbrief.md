# RAGKA v1r1 Memory Clean - Project Brief

## Project Overview
RAGKA v1r1 is a sophisticated Retrieval-Augmented Generation (RAG) system with intelligent query routing, conversation management, and advanced pattern matching capabilities. The system is currently deployed on Azure with PostgreSQL database, Azure OpenAI services, and Azure Cognitive Search.

## Core Requirements
- **Primary Goal**: Implement Redis caching to improve performance and reduce API costs
- **Critical Constraint**: System is already working in production - changes must be reversible
- **Performance Target**: Reduce response times and API costs while maintaining accuracy
- **Scalability Need**: Support for concurrent users and high-volume queries

## Current Architecture
- **Backend**: Flask application with RAG Assistant v2
- **Database**: PostgreSQL on Azure
- **AI Services**: Azure OpenAI (GPT-4o, GPT-4o-mini, embeddings)
- **Search**: Azure Cognitive Search with vector indexing
- **Deployment**: Docker containers with Gunicorn
- **Session Management**: In-memory session storage per container

## Key Components
1. **Intelligent Query Router**: Pattern matching + GPT-4 fallback for intent classification
2. **Conversation Manager**: Maintains chat history with summarization
3. **Enhanced Pattern Matcher**: Regex-based query classification
4. **Query Mediator**: LLM-based mediation for low-confidence classifications
5. **Context Analyzer**: Conversation context analysis
6. **Knowledge Base Search**: Vector search with hierarchical retrieval

## Success Criteria
- Maintain current functionality and accuracy
- Achieve 40% reduction in GPT-4 API calls
- Improve response times by 25% for cached queries
- Support system rollback within minutes if needed
- Zero downtime deployment capability

## Risk Mitigation
- Phased implementation with fallback mechanisms
- Comprehensive testing at each phase
- Performance monitoring and alerting
- Automated rollback procedures
