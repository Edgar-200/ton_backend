"""
TON — NikoScore Admin

NikoScore rows are READ-ONLY in admin — they must never be manually edited.
Always recalculated by the engine from nikoscore_events.
NikoScoreEvent rows are also read-only — immutable audit log.
"""

from django.contrib import admin
from .models import NikoScore, NikoScoreEvent


@admin.register(NikoScore)
class NikoScoreAdmin(admin.ModelAdmin):
    list_display = (
        'student', 'total_score', 'component_profile', 'component_activity',
        'component_quality', 'component_reliability',
        'calculation_version', 'last_calculated_at',
    )
    search_fields = ('student__full_name', 'student__user__email')
    readonly_fields = (
        'id', 'student', 'total_score',
        'component_profile', 'component_activity',
        'component_quality', 'component_reliability',
        'last_calculated_at', 'calculation_version',
    )
    ordering = ('-total_score',)

    # Prevent any manual edits — engine only
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False  # Read-only — engine manages all updates


@admin.register(NikoScoreEvent)
class NikoScoreEventAdmin(admin.ModelAdmin):
    list_display = (
        'student', 'event_type', 'component',
        'delta', 'score_before', 'score_after', 'created_at',
    )
    list_filter = ('event_type', 'component')
    search_fields = ('student__full_name', 'reason')
    readonly_fields = (
        'id', 'student', 'event_type', 'component',
        'delta', 'score_before', 'score_after',
        'reason', 'source_id', 'created_at',
    )
    ordering = ('-created_at',)

    # Immutable audit log — no add, change, or delete
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
