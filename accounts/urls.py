from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from . import views


urlpatterns = [
    path(
        "register/",
        views.AuthViewSet.as_view({
            "post": "register",
        }),
        name="register",
    ),

    path(
        "me/",
        views.AuthViewSet.as_view({
            "get": "me",
        }),
        name="me",
    ),

    path(
        "token/",
        TokenObtainPairView.as_view(),
        name="token-obtain-pair",
    ),

    path(
        "token/refresh/",
        TokenRefreshView.as_view(),
        name="token-refresh",
    ),
]