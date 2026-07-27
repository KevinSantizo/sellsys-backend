from django.urls import path

from .views import SaleViewSet


app_name = "sales"


sale_list_view = (
    SaleViewSet.as_view({
        "get": "list",
    })
)

sale_checkout_view = (
    SaleViewSet.as_view({
        "post": "checkout",
    })
)

sale_detail_view = (
    SaleViewSet.as_view({
        "get": "retrieve",
    })
)


urlpatterns = [
    path(
        "",
        sale_list_view,
        name="sale-list",
    ),
    path(
        "checkout/",
        sale_checkout_view,
        name="sale-checkout",
    ),
    path(
        "<uuid:pk>/",
        sale_detail_view,
        name="sale-detail",
    ),
]