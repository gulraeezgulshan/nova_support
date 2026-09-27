"""FastAPI application entry point: `uvicorn src.main:app`."""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from complaint_processing.service import ComplaintValidationError, DuplicateComplaintError
from document_processing.validation import DocumentValidationError
from knowledge_base.service import DuplicateDocumentError
from knowledge_base.versioning import VersionTransitionError
from src.api.routes import (
    analytics,
    attachments,
    chat,
    complaints,
    contact,
    documents,
    health,
    imports,
    mailbox,
    review,
    rules,
    storefront,
    taxonomy,
    users,
    webhooks,
)
from src.core.config import get_settings
from src.core.logging import configure_logging


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level, json=settings.environment == "production")

    app = FastAPI(
        title="SupportNova API",
        version="0.1.0",
        description="Complaint intelligence: GenAI analysis + Python ground-truth validation.",
        docs_url="/docs" if settings.environment != "production" else None,
        # Operation IDs = handler names, so the generated TypeScript client reads naturally.
        generate_unique_id_function=lambda route: route.name,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,  # auth uses the Authorization header, not cookies
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["Content-Disposition"],  # file names of report exports
    )

    app.include_router(health.router)
    for router in (
        users.router,
        taxonomy.router,
        documents.router,
        imports.router,
        mailbox.router,
        complaints.router,
        review.router,
        analytics.router,
        attachments.router,
        storefront.router,
        chat.router,
        contact.router,
        rules.router,
        webhooks.router,
    ):
        app.include_router(router, prefix=settings.api_prefix)

    @app.exception_handler(DocumentValidationError)
    async def _validation_error(_: Request, exc: DocumentValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": "Document failed validation", "issues": exc.issues},
        )

    @app.exception_handler(DuplicateDocumentError)
    async def _duplicate(_: Request, exc: DuplicateDocumentError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})

    @app.exception_handler(ComplaintValidationError)
    async def _complaint_invalid(_: Request, exc: ComplaintValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": "Complaint failed validation", "issues": exc.issues},
        )

    @app.exception_handler(DuplicateComplaintError)
    async def _complaint_duplicate(_: Request, exc: DuplicateComplaintError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc), "existing_ref": exc.existing_ref},
        )

    @app.exception_handler(VersionTransitionError)
    async def _transition(_: Request, exc: VersionTransitionError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})

    return app


app = create_app()
