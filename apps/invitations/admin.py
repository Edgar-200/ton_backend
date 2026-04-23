"""
TON — Invitations Admin

contact_released is visible in admin for dispute resolution.
Admin can see student contact details here regardless of invitation status.
This is intentional — admin needs full visibility for governance.
"""

from django.contrib import admin
from .models import Invitation


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = (
        'company', 'student', 'invitation_type',
        'status', 'contact_released', 'sent_at', 'expires_at',
    )
    list_filter = ('status', 'invitation_type', 'contact_released')
    search_fields = (
        'company__company_name',
        'student__full_name',
        'student__user__email',
    )
    readonly_fields = ('id', 'sent_at', 'viewed_at', 'responded_at')
    ordering = ('-sent_at',)

    fieldsets = (
        ('Parties', {
            'fields': ('id', 'company', 'student')
        }),
        ('Invitation', {
            'fields': ('invitation_type', 'message', 'status', 'contact_released')
        }),
        ('Expiry', {
            'fields': ('expires_at',)
        }),
        ('Timeline', {
            'fields': ('sent_at', 'viewed_at', 'responded_at'),
            'classes': ('collapse',),
        }),
    )
