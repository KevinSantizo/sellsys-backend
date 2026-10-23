from django.conf import settings
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)
from django.db import connection

def health_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return JsonResponse(
            {
                "status": "error",
                "application": "SellSys",
                "database": "unavailable",
            },
            status=503,
        )

    return JsonResponse({
        "status": "ok",
        "application": "SellSys",
        "database": "ok",
    })


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/health/",  health_check),
    path("api/v1/auth/", include("accounts.urls")),
    path("api/v1/",  include("companies.urls")),
    path("api/v1/branches/",  include("branches.urls")),
    path("api/v1/catalog/", include("catalog.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/v1/branch-memberships/", include("branches.membership_urls")),
    path("api/v1/sales/", include("sales.urls")),
    path("api/v1/purchases/", include("purchases.urls"),),
    path("api/v1/expenses/", include("expenses.urls")),
    path("api/v1/cash/", include("cash.urls")),
    path("api/v1/reports/", include("reports.urls")),
]

if settings.ENABLE_API_DOCS:
    urlpatterns += [
        path(
            "api/schema/",
            SpectacularAPIView.as_view(),
            name="schema",
        ),
        path(
            "api/docs/",
            SpectacularSwaggerView.as_view(
                url_name="schema"
            ),
            name="swagger-ui",
        ),
    ]