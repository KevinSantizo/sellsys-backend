from django.urls import path

from .views import PurchaseViewSet, SupplierViewSet


app_name = "purchases"


supplier_list_view = SupplierViewSet.as_view({
    "get": "list",
    "post": "create",
})

supplier_detail_view = SupplierViewSet.as_view({
    "get": "retrieve",
    "patch": "partial_update",
    "put": "update",
})

purchase_list_view = PurchaseViewSet.as_view({
    "get": "list",
    "post": "create",
})

purchase_detail_view = PurchaseViewSet.as_view({
    "get": "retrieve",
    "patch": "partial_update",
    "put": "update",
})

purchase_complete_view = PurchaseViewSet.as_view({
    "post": "complete",
})

purchase_cancel_view = PurchaseViewSet.as_view({
    "post": "cancel",
})

urlpatterns = [
    path("suppliers/", supplier_list_view, name="supplier-list",),
    path("suppliers/<uuid:pk>/", supplier_detail_view, name="supplier-detail", ),
    path("", purchase_list_view, name="purchase-list"),
    path("<uuid:pk>/", purchase_detail_view, name="purchase-detail"),
    path("<uuid:pk>/complete/", purchase_complete_view, name="purchase-complete",),
    path("<uuid:pk>/cancel/", purchase_cancel_view, name="purchase-cancel"),
]