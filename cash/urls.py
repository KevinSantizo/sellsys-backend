from django.urls import path

from .views import CashRegisterViewSet, CashSessionViewSet, CashMovementViewSet


cash_register_list_view = CashRegisterViewSet.as_view({ "get": "list", "post": "create" })
cash_register_detail_view = CashRegisterViewSet.as_view({ "get": "retrieve", "patch": "partial_update", "put": "update" })
cash_session_list_view = CashSessionViewSet.as_view({ "get": "list" })
cash_session_detail_view = CashSessionViewSet.as_view({ "get": "retrieve" })
cash_session_open_view = CashSessionViewSet.as_view({ "post": "open_session" })
cash_session_close_view = CashSessionViewSet.as_view({ "post": "close_session" })
cash_movement_list_view = CashMovementViewSet.as_view({ "get": "list" })
cash_movement_detail_view = CashMovementViewSet.as_view({ "get": "retrieve" })
cash_movement_manual_view = CashMovementViewSet.as_view({ "post": "manual" })
cash_session_summary_view = CashSessionViewSet.as_view({ "get": "summary" })

urlpatterns = [
    path("registers/", cash_register_list_view, name="cash-register-list"),
    path("registers/<uuid:pk>/", cash_register_detail_view, name="cash-register-detail"),
    path("sessions/", cash_session_list_view, name="cash-session-list"),
    path("sessions/open/", cash_session_open_view, name="cash-session-open"),
    path("sessions/<uuid:pk>/", cash_session_detail_view, name="cash-session-detail"),
    path("sessions/<uuid:pk>/close/", cash_session_close_view, name="cash-session-close"),
    path("movements/", cash_movement_list_view, name="cash-movement-list"),
    path("movements/manual/", cash_movement_manual_view, name="cash-movement-manual"),
    path("movements/<uuid:pk>/", cash_movement_detail_view, name="cash-movement-detail"),
    path("sessions/<uuid:pk>/summary/", cash_session_summary_view, name="cash-session-summary"),
]