import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.errors import (
    ConfigurationError,
    GroundedError,
    ProviderError,
)

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """Register controlled error handlers on the FastAPI app.

    We return safe, generic messages to the client and log the real detail
    server-side. We never echo internal exceptions or provider messages back
    to the user.
    """

    @app.exception_handler(GroundedError)
    async def _grounded_error_handler(
        request: Request, exc: GroundedError
    ) -> JSONResponse:
        logger.warning(
            "GroundedError on %s %s: %s",
            request.method,
            request.url.path,
            exc.message,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message},
        )

    @app.exception_handler(ConfigurationError)
    async def _config_error_handler(
        request: Request, exc: ConfigurationError
    ) -> JSONResponse:
        return await _grounded_error_handler(request, exc)

    @app.exception_handler(ProviderError)
    async def _provider_error_handler(
        request: Request, exc: ProviderError
    ) -> JSONResponse:
        logger.error(
            "ProviderError on %s %s: %s", request.method, request.url.path, exc
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message},
        )