from django.urls import path
from .views import SaleViewSet, CustomerViewSet


app_name = "sales"

sale_list_view = (SaleViewSet.as_view({ "get": "list", }))
sale_checkout_view = (SaleViewSet.as_view({ "post": "checkout", }))
sale_detail_view = (SaleViewSet.as_view({ "get": "retrieve", }))
sale_weekly_summary_view = (SaleViewSet.as_view({ "get": "weekly_summary", }))
sale_yearly_summary_view = (SaleViewSet.as_view({ "get": "yearly_summary", }))
sale_cancel_view = SaleViewSet.as_view({ "post": "cancel" })
sale_receipt_view = SaleViewSet.as_view({ "get": "receipt" })
customer_list_view = CustomerViewSet.as_view({ "get": "list", "post": "create", })
customer_detail_view = CustomerViewSet.as_view({ "get": "retrieve", "put": "update", "patch": "partial_update", })
sale_payment_view = SaleViewSet.as_view({"post": "add_payment"})
sale_accounts_receivable_view = SaleViewSet.as_view({ "get": "accounts_receivable", })

urlpatterns = [
    path("", sale_list_view, name="sale-list",),
    path("checkout/", sale_checkout_view, name="sale-checkout",),
    path("weekly-summary/", sale_weekly_summary_view, name="sale-weekly-summary",),
    path("yearly-summary/", sale_yearly_summary_view, name="sale-yearly-summary",),
    path("<uuid:pk>/", sale_detail_view, name="sale-detail",),
    path("<uuid:pk>/cancel/", sale_cancel_view, name="sale-cancel"),
    path("<uuid:pk>/receipt/", sale_receipt_view, name="sale-receipt"),
    path("customers/", customer_list_view, name="customer-list",),
    path("customers/<uuid:pk>/", customer_detail_view, name="customer-detail",),
    path("<uuid:pk>/payments/", sale_payment_view, name="sale-payment",),
    path( "accounts-receivable/", sale_accounts_receivable_view,  name="sale-accounts-receivable"),
] 