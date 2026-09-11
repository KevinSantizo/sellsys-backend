from django.urls import path

from .views import (
    ExpenseCategoryViewSet,
    ExpenseViewSet,
)


app_name = "expenses"


expense_category_list_view = (ExpenseCategoryViewSet.as_view({"get": "list", "post": "create",}))
expense_category_detail_view = (ExpenseCategoryViewSet.as_view({"get": "retrieve", "patch": "partial_update", "put": "update",}))
expense_complete_view = (ExpenseViewSet.as_view({"post": "complete",}))
expense_cancel_view = (ExpenseViewSet.as_view({"post": "cancel",}))
expense_list_view = ExpenseViewSet.as_view({ "get": "list", "post": "create" })
expense_detail_view = ExpenseViewSet.as_view({ "get": "retrieve", "patch": "partial_update", "put": "update" })

urlpatterns = [
    path(
        "categories/",
        expense_category_list_view,
        name="expense-category-list",
    ),

    path(
        "categories/<uuid:pk>/",
        expense_category_detail_view,
        name="expense-category-detail",
    ),

    path(
        "",
        expense_list_view,
        name="expense-list",
    ),

    path(
        "<uuid:pk>/",
        expense_detail_view,
        name="expense-detail",
    ),

    path(
        "<uuid:pk>/complete/",
        expense_complete_view,
        name="expense-complete",
    ),

    path(
        "<uuid:pk>/cancel/",
        expense_cancel_view,
        name="expense-cancel",
    ),
]