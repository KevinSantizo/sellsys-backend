from django.urls import path

from . import views


urlpatterns = [
    path(
        "categories/",
        views.CategoryViewSet.as_view({
            "get": "list",
            "post": "create",
        }),
        name="category-list-create",
    ),

    path(
        "categories/<uuid:pk>/",
        views.CategoryViewSet.as_view({
            "get": "retrieve",
            "put": "update",
            "patch": "partial_update",
            "delete": "destroy",
        }),
        name="category-detail",
    ),

    path(
        "brands/",
        views.BrandViewSet.as_view({
            "get": "list",
            "post": "create",
        }),
        name="brand-list-create",
    ),

    path(
        "brands/<uuid:pk>/",
        views.BrandViewSet.as_view({
            "get": "retrieve",
            "put": "update",
            "patch": "partial_update",
            "delete": "destroy",
        }),
        name="brand-detail",
    ),

    path(
        "units/",
        views.UnitOfMeasureViewSet.as_view({
            "get": "list",
            "post": "create",
        }),
        name="unit-list-create",
    ),

    path(
        "units/<uuid:pk>/",
        views.UnitOfMeasureViewSet.as_view({
            "get": "retrieve",
            "put": "update",
            "patch": "partial_update",
            "delete": "destroy",
        }),
        name="unit-detail",
    ),

    path(
        "products/",
        views.ProductViewSet.as_view({
            "get": "list",
            "post": "create",
        }),
        name="product-list-create",
    ),

    path(
        "products/upload-image/",
        views.ProductViewSet.as_view({
            "post": "upload_image",
        }),
        name="product-upload-image",
    ),

    path(
        "products/<uuid:pk>/",
        views.ProductViewSet.as_view({
            "get": "retrieve",
            "put": "update",
            "patch": "partial_update",
            "delete": "destroy",
        }),
        name="product-detail",
    ),

]