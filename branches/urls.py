from django.urls import path

from . import views


urlpatterns = [
    path(
        "",
        views.BranchViewSet.as_view({
            "get": "list",
            "post": "create",
        }),
        name="branch-list-create",
    ),

    path(
        "memberships/",
        views.BranchMembershipViewSet.as_view({
            "get": "list",
            "post": "create",
        }),
        name="branch-membership-list-create",
    ),

    path(
        "memberships/<uuid:pk>/",
        views.BranchMembershipViewSet.as_view({
            "get": "retrieve",
            "put": "update",
            "patch": "partial_update",
            "delete": "destroy",
        }),
        name="branch-membership-detail",
    ),

    path(
        "<uuid:pk>/",
        views.BranchViewSet.as_view({
            "get": "retrieve",
            "put": "update",
            "patch": "partial_update",
            "delete": "destroy",
        }),
        name="branch-detail",
    ),
]