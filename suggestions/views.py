from rest_framework.generics import CreateAPIView
from rest_framework.permissions import IsAuthenticated

from .models import Suggestion
from .serializers import SuggestionSerializer


# Create your views here.

class SuggestionCreateView(CreateAPIView):
    queryset = Suggestion.objects.all()
    serializer_class = SuggestionSerializer
    permission_classes = (
        IsAuthenticated,
    )

    def perform_create(self, serializer):
        serializer.save(
            created_by=self.request.user,
        )