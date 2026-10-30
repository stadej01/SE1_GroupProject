from django.db import models
from django.contrib.auth.models import AbstractUser

from .managers import UserManager

# Create your models here.


class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=150)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["display_name"]

    objects = UserManager()
