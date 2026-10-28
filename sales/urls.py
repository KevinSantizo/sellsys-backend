from django.urls import path
from .views import SaleViewSet


app_name = "sales"

sale_list_view = (SaleViewSet.as_view({ "get": "list", }))
sale_checkout_view = (SaleViewSet.as_view({ "post": "checkout", }))
sale_detail_view = (SaleViewSet.as_view({ "get": "retrieve", }))
sale_weekly_summary_view = (SaleViewSet.as_view({ "get": "weekly_summary", }))
sale_yearly_summary_view = (SaleViewSet.as_view({ "get": "yearly_summary", }))
sale_cancel_view = SaleViewSet.as_view({ "post": "cancel" })
sale_receipt_view = SaleViewSet.as_view({ "get": "receipt" })


urlpatterns = [
    path("", sale_list_view, name="sale-list",),
    path("checkout/", sale_checkout_view, name="sale-checkout",),
    path("weekly-summary/", sale_weekly_summary_view, name="sale-weekly-summary",),
    path("yearly-summary/", sale_yearly_summary_view, name="sale-yearly-summary",),
    path("<uuid:pk>/", sale_detail_view, name="sale-detail",),
    path("<uuid:pk>/cancel/", sale_cancel_view, name="sale-cancel"),
    path("<uuid:pk>/receipt/", sale_receipt_view, name="sale-receipt"),

] 