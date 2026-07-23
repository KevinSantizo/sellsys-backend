from django.urls import path

from . import views


urlpatterns = [
    path(
        "",
        views.BranchViewSet.as_view({
            "get": "list",
            "post": "create",
        }),
    ),
    path(
        "<uuid:pk>/",
        views.BranchViewSet.as_view({
            "get": "retrieve",
            "put": "update",
            "patch": "partial_update",
            "delete": "destroy",
        }),
    ),
]