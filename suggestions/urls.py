from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import SuggestionCreateView


router = DefaultRouter()
 
urlpatterns = [
    path(
        "suggestions/",
        SuggestionCreateView.as_view(),
        name="suggestion-create",
    ),
]