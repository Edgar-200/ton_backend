"""
TON — Email Authentication Backend

Django's default auth backend uses `username` field.
TON uses `email` as the login identifier — this backend makes
django.contrib.auth.authenticate(email=..., password=...) work correctly.
"""

from django.contrib.auth.backends import ModelBackend
from apps.authentication.models import User


class EmailBackend(ModelBackend):
    """
    Authenticates against email + password.
    Used by LoginSerializer via django.contrib.auth.authenticate().
    """

    def authenticate(self, request, email=None, password=None, **kwargs):
        if not email or not password:
            return None
        try:
            user = User.objects.get(email=email.lower())
        except User.DoesNotExist:
            # Run the default password hasher to prevent timing attacks
            User().set_password(password)
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
