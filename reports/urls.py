from django.urls import path

from .views import CashReportView, ExpensesReportView, PurchasesReportView, ReportDailyView, ReportSummaryView, SalesReportView, InventoryReportView, ProfitabilityReportView

urlpatterns = [
    path("summary/", ReportSummaryView.as_view(), name="report-summary"),
    path("daily/", ReportDailyView.as_view(), name="report-daily"),
    path("sales/", SalesReportView.as_view(), name="report-sales"),
    path("purchases/", PurchasesReportView.as_view(), name="report-purchases"),
    path("expenses/", ExpensesReportView.as_view(), name="report-expenses"),
    path("cash/", CashReportView.as_view(), name="report-cash"),
    path("inventory/", InventoryReportView.as_view(), name="report-inventory"),
    path("profitability/", ProfitabilityReportView.as_view(), name="report-profitability"),
]


