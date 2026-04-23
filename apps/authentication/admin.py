"""
TON — Authentication Admin

Registers User and PasswordResetToken models in the Django admin.
All admin actions are logged at the application level via admin_panel views.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, PasswordResetToken


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'role', 'is_verified', 'is_active', 'phone', 'created_at')
    list_filter = ('role', 'is_verified', 'is_active')
    search_fields = ('email', 'phone')
    ordering = ('-created_at',)
    readonly_fields = ('id', 'created_at', 'updated_at', 'last_active_at', 'otp_attempts')

    fieldsets = (
        ('Identity', {'fields': ('id', 'email', 'password', 'phone', 'role')}),
        ('Verification', {'fields': ('is_verified', 'otp_code', 'otp_expires_at', 'otp_attempts')}),
        ('Status', {'fields': ('is_active', 'is_staff', 'is_superuser')}),
        ('Activity', {'fields': ('last_active_at', 'created_at', 'updated_at')}),
        ('Permissions', {'fields': ('groups', 'user_permissions')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'role', 'phone'),
        }),
    )

    # Override BaseUserAdmin — uses email not username
    filter_horizontal = ('groups', 'user_permissions')


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at', 'expires_at', 'used')
    list_filter = ('used',)
    search_fields = ('user__email',)
    readonly_fields = ('id', 'user', 'token', 'created_at', 'expires_at')
    ordering = ('-created_at',)
