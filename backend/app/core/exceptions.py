"""Errores de negocio y su traduccion HTTP uniforme `{code, message, details}`."""

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "app_error"

    def __init__(
        self,
        message: str,
        details: dict | list | str | None = None,
        headers: dict[str, str] | None = None,
    ):
        self.message = message
        self.details = details
        self.headers = headers
        super().__init__(message)


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


class ValidationAppError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "validation_error"


class RateLimitedError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limited"


class UpstreamError(AppError):
    """Servicio externo (Leo/Incubus) no disponible o con respuesta inesperada."""

    status_code = status.HTTP_502_BAD_GATEWAY
    code = "upstream_unavailable"


def body(code: str, message: str, details) -> dict:
    return {"code": code, "message": message, "details": details}


def _app_error_handler(_r: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=body(exc.code, exc.message, exc.details),
        headers=exc.headers,
    )


def _validation_handler(_r: Request, exc: RequestValidationError) -> JSONResponse:
    # Solo campo y mensaje: nunca se devuelve el valor recibido (contrasenas, etc.).
    details = [
        {"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]}
        for e in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=body("validation_error", "Revisa los datos enviados.", details),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_handler)
