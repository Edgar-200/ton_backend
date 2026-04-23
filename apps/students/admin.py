"""
TON — Students Admin

Registers StudentProfile in Django admin.
DIT verification queue is managed via the platform's own admin panel
(/api/admin/students/pending-dit/) for better workflow, but this
provides a fallback for superusers.
"""

from django.contrib import admin
from .models import StudentProfile


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = (
        'full_name', 'dit_student_id', 'course', 'year_of_study',
        'verification_status', 'profile_completion_pct', 'is_deleted', 'created_at',
    )
    list_filter = ('verification_status', 'course', 'year_of_study', 'is_deleted')
    search_fields = ('full_name', 'dit_student_id', 'user__email')
    readonly_fields = (
        'id', 'created_at', 'updated_at', 'profile_completion_pct',
        'user',
    )
    ordering = ('-created_at',)

    fieldsets = (
        ('Identity', {
            'fields': ('id', 'user', 'full_name', 'dit_student_id')
        }),
        ('Academic', {
            'fields': ('course', 'year_of_study', 'sectors')
        }),
        ('Profile', {
            'fields': ('bio', 'profile_photo_url', 'profile_completion_pct')
        }),
        ('DIT Verification', {
            'fields': (
                'dit_id_document_url',
                'verification_status',
                'verification_note',
            )
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

    actions = ['mark_verified', 'mark_rejected']

    def mark_verified(self, request, queryset):
        queryset.update(verification_status='verified')
        self.message_user(request, f'{queryset.count()} student(s) marked as verified.')
    mark_verified.short_description = 'Mark selected students as DIT verified'

    def mark_rejected(self, request, queryset):
        queryset.update(verification_status='rejected')
        self.message_user(request, f'{queryset.count()} student(s) marked as rejected.')
    mark_rejected.short_description = 'Mark selected students as rejected'
