from django.contrib.auth import get_user_model
from django.test import TestCase

from rest_framework import status
from rest_framework.test import APIClient


User = get_user_model()


class AuthenticationTests(TestCase):

    def setUp(self):
        self.client = APIClient()

        self.password = "SellSys123!"

        self.user = User.objects.create_user(
            email="tests@sellsys.com",
            password=self.password,
            first_name="Test",
            last_name="User",
        )

    def test_login_returns_access_and_refresh_tokens(self):
        response = self.client.post(
            "/api/v1/auth/token/",
            {
                "email": self.user.email,
                "password": self.password,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_login_with_invalid_password_returns_401(self):
        response = self.client.post(
            "/api/v1/auth/token/",
            {
                "email": self.user.email,
                "password": "incorrect-password",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_without_token_returns_401(self):
        response = self.client.get(
            "/api/v1/auth/me/",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_with_valid_token_returns_current_user(self):
        login_response = self.client.post(
            "/api/v1/auth/token/",
            {
                "email": self.user.email,
                "password": self.password,
            },
            format="json",
        )

        access_token = login_response.data["access"]

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {access_token}"
        )

        response = self.client.get(
            "/api/v1/auth/me/",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], self.user.email)

    def test_refresh_token_returns_new_access_token(self):
        login_response = self.client.post(
            "/api/v1/auth/token/",
            {
                "email": self.user.email,
                "password": self.password,
            },
            format="json",
        )

        refresh_token = login_response.data["refresh"]

        response = self.client.post(
            "/api/v1/auth/token/refresh/",
            {
                "refresh": refresh_token,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_inactive_user_cannot_login(self):
        self.user.is_active = False
        self.user.save(update_fields=[ "is_active" ])

        response = self.client.post(
            "/api/v1/auth/token/",
            {
                "email": self.user.email,
                "password": self.password,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)