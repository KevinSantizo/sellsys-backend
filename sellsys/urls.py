from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)


def health_check(request):
    return JsonResponse({
        "status": "ok",
        "application": "SellSys",
    })


urlpatterns = [
    path("admin/", admin.site.urls),

    path(
        "api/v1/health/",
        health_check,
    ),

    path(
        "api/v1/auth/",
        include("accounts.urls"),
    ),

    path(
        "api/v1/",
        include("companies.urls"),
    ),

    path(
        "api/v1/branches/",
        include("branches.urls"),
    ),

    path(
        "api/v1/catalog/",
        include("catalog.urls"),
    ),

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

    path(
        "api/v1/branch-memberships/",
        include("branches.membership_urls"),
    ),

    path(
        "api/v1/sales/",
        include("sales.urls"),
    ),

]