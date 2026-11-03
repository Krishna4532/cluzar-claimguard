from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.documents import router as documents_router
from app.api.retrieval import router as retrieval_router
from app.api.verifications import router as verifications_router
from app.api.reviews import router as reviews_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="ClaimGuard - AI-powered RAG system that verifies claims in AI-generated marketing content against approved documents.",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Set all CORS enabled origins for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(documents_router)
app.include_router(retrieval_router)
app.include_router(verifications_router)
app.include_router(reviews_router)


@app.get("/", tags=["Root"])
def root():
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "online",
        "description": "AI-powered claim verification RAG system",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "environment": settings.APP_ENV,
        "version": settings.VERSION,
    }

