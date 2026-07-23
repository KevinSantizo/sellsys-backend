from django.contrib.auth.models import AbstractUser
from django.db import models

from common.models import BaseModel
from .managers import UserManager

# Create your models here.

class User(BaseModel, AbstractUser):
    username = None
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=30, blank=True)
    is_platform_admin = models.BooleanField(default=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email