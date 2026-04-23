"""
TON — Companies Admin

Registers Company and Watchlist in Django admin.
Company verification queue is better managed via /api/admin/companies/pending/
but this provides superuser fallback access.
"""

from django.contrib import admin
from .models import Company, Watchlist


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = (
        'company_name', 'brela_number', 'sector',
        'verification_status', 'onboarding_stage', 'is_deleted', 'created_at',
    )
    list_filter = ('verification_status', 'sector', 'onboarding_stage', 'is_deleted')
    search_fields = ('company_name', 'brela_number', 'user__email', 'contact_person')
    readonly_fields = ('id', 'user', 'created_at', 'updated_at')
    ordering = ('-created_at',)

    fieldsets = (
        ('Identity', {
            'fields': ('id', 'user', 'company_name', 'brela_number', 'sector', 'contact_person')
        }),
        ('Media', {
            'fields': ('logo_url', 'website', 'brela_document_url')
        }),
        ('Verification', {
            'fields': ('verification_status', 'verification_note', 'onboarding_stage')
        }),
        ('Soft Delete', {
            'fields': ('is_deleted', 'deleted_at'),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    actions = ['approve_companies', 'reject_companies']

    def approve_companies(self, request, queryset):
        queryset.update(verification_status='verified')
        self.message_user(request, f'{queryset.count()} company/companies approved.')
    approve_companies.short_description = 'Approve selected companies'

    def reject_companies(self, request, queryset):
        queryset.update(verification_status='rejected')
        self.message_user(request, f'{queryset.count()} company/companies rejected.')
    reject_companies.short_description = 'Reject selected companies'


@admin.register(Watchlist)
class WatchlistAdmin(admin.ModelAdmin):
    list_display = ('company', 'student', 'saved_at')
    search_fields = ('company__company_name', 'student__full_name')
    readonly_fields = ('id', 'saved_at')
    ordering = ('-saved_at',)
