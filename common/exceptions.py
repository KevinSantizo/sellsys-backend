import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        return response

    request = context.get("request")
    view = context.get("view")

    logger.exception(
        "Unhandled API exception. method=%s path=%s view=%s user_id=%s",
        getattr(request, "method", None),
        getattr(request, "path", None),
        view.__class__.__name__ if view else None,
        getattr(getattr(request, "user", None), "id", None),
        exc_info=exc,
    )

    return Response(
        {
            "detail": "Ocurrió un error interno. Inténtalo nuevamente."
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )