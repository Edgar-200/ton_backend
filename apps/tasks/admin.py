"""
TON — Tasks Admin

Registers Task and Submission in Django admin.
company_feedback is included here for admin visibility — it is still
excluded from all student-facing API serializers.
"""

from django.contrib import admin
from .models import Task, Submission


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = (
        'title', 'company', 'sector', 'status',
        'submissions_count', 'deadline', 'is_deleted', 'created_at',
    )
    list_filter = ('status', 'sector', 'is_deleted')
    search_fields = ('title', 'company__company_name', 'sector')
    readonly_fields = ('id', 'submissions_count', 'created_at', 'updated_at')
    ordering = ('-created_at',)

    fieldsets = (
        ('Task', {
            'fields': ('id', 'company', 'title', 'description', 'sector', 'skill_tags')
        }),
        ('Settings', {
            'fields': ('deadline', 'status', 'max_submissions', 'submissions_count')
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


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = (
        'student', 'task', 'status', 'company_score',
        'nikoscore_processed', 'submitted_at',
    )
    list_filter = ('status', 'nikoscore_processed')
    search_fields = (
        'student__full_name', 'task__title', 'student__user__email'
    )
    readonly_fields = ('id', 'submitted_at', 'created_at', 'updated_at')
    ordering = ('-submitted_at',)

    fieldsets = (
        ('Submission', {
            'fields': ('id', 'task', 'student', 'status')
        }),
        ('Content', {
            'fields': ('content_text', 'file_url', 'external_link')
        }),
        ('Company Review', {
            'fields': ('company_score', 'company_feedback', 'reviewed_at')
        }),
        ('NikoScore', {
            'fields': ('nikoscore_processed',)
        }),
        ('Timestamps', {
            'fields': ('submitted_at', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
