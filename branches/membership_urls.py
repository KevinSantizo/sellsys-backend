from django.urls import path

from . import views


urlpatterns = [
    path(
        "",
        views.BranchMembershipViewSet.as_view({
            "get": "list",
            "post": "create",
        }),
        name="branch-membership-list-create",
    ),

    path(
        "<uuid:pk>/",
        views.BranchMembershipViewSet.as_view({
            "get": "retrieve",
            "put": "update",
            "patch": "partial_update",
            "delete": "destroy",
        }),
        name="branch-membership-detail",
    ),
]