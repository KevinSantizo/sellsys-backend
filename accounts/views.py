from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from companies.serializers import CompanyDetailSerializer

from .serializers import (
    RegisterSerializer,
    UserDetailSerializer,
)


class AuthViewSet(ViewSet):
    def get_permissions(self):
        if self.action == "register":
            return [AllowAny()]

        return [IsAuthenticated()]

    def register(self, request):
        serializer = RegisterSerializer(
            data=request.data,
        )

        serializer.is_valid(
            raise_exception=True,
        )

        user = serializer.save()

        return Response(
            {
                "message": "Cuenta creada correctamente.",
                "user": UserDetailSerializer(
                    user,
                ).data,
                "company": CompanyDetailSerializer(
                    serializer.company,
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )

    def me(self, request):
        return Response(
            UserDetailSerializer(
                request.user,
            ).data,
        )