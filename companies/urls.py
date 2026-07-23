from django.urls import path

from . import views


urlpatterns = [
    path(
        "companies/",
        views.CompanyViewSet.as_view({
            "get": "list",
            "post": "create",
        }),
    ),
    path(
        "companies/<uuid:pk>/",
        views.CompanyViewSet.as_view({
            "get": "retrieve",
            "put": "update",
            "patch": "partial_update",
            "delete": "destroy",
        }),
    ),

    path(
        "company-memberships/",
        views.CompanyMembershipViewSet.as_view({
            "get": "list",
            "post": "create",
        }),
    ),
    path(
        "company-memberships/<uuid:pk>/",
        views.CompanyMembershipViewSet.as_view({
            "get": "retrieve",
            "put": "update",
            "patch": "partial_update",
            "delete": "destroy",
        }),
    ),

    path(
        "company-settings/",
        views.CompanySettingsViewSet.as_view({
            "get": "list",
            "post": "create",
        }),
    ),
    path(
        "company-settings/<uuid:pk>/",
        views.CompanySettingsViewSet.as_view({
            "get": "retrieve",
            "put": "update",
            "patch": "partial_update",
            "delete": "destroy",
        }),
    ),

    path(
        "modules/",
        views.ModuleViewSet.as_view({
            "get": "list",
            "post": "create",
        }),
    ),
    path(
        "modules/<uuid:pk>/",
        views.ModuleViewSet.as_view({
            "get": "retrieve",
            "put": "update",
            "patch": "partial_update",
            "delete": "destroy",
        }),
    ),

    path(
        "company-modules/",
        views.CompanyModuleViewSet.as_view({
            "get": "list",
            "post": "create",
        }),
    ),
    path(
        "company-modules/<uuid:pk>/",
        views.CompanyModuleViewSet.as_view({
            "get": "retrieve",
            "put": "update",
            "patch": "partial_update",
            "delete": "destroy",
        }),
    ),
]