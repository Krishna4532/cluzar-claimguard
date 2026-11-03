# ClaimGuard

**ClaimGuard** is an AI-powered RAG system designed to verify claims made in AI-generated marketing content against a business's approved knowledge base and factual documentation.

## Project Structure

```text
claimguard/
├── backend/
│   ├── app/
│   │   ├── api/            # API routes and endpoints
│   │   ├── core/           # Core configurations and settings
│   │   ├── db/             # Database connection, models, and migrations
│   │   ├── ingestion/      # Document ingestion and processing
│   │   ├── retrieval/      # Semantic search and vector retrieval
│   │   ├── pipeline/       # Claim verification workflow orchestration
│   │   ├── schemas/        # Pydantic models for request/response schemas
│   │   └── services/       # Business logic services
│   ├── tests/              # Backend test suite
│   ├── requirements.txt    # Base backend dependencies
│   └── requirements-rag.txt# RAG, embedding, and orchestration dependencies
├── eval/
│   ├── data/               # Evaluation datasets and ground truth
│   └── reports/            # Evaluation benchmarks and results
├── docs/                   # Documentation and architecture diagrams
├── frontend/               # Frontend UI (planned)
├── docker-compose.yml      # Local PostgreSQL + pgvector container definition
├── .env.example            # Environment variables template
├── .gitignore              # Git ignore rules
└── README.md
```

## Quick Start

### 1. Python Environment Setup

Navigate to the `backend` directory and activate the virtual environment:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
```

### 2. Install Dependencies

```powershell
pip install -r requirements.txt
```

### 3. Run FastAPI Backend

```powershell
uvicorn app.main:app --reload --port 8000
```
Visit http://127.0.0.1:8000/docs for the interactive Swagger API documentation.

