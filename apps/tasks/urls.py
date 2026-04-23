from django.urls import path
from .views import (
    TaskFeedView,
    TaskDetailView,
    TaskCreateView,
    TaskCloseView,
    SubmissionCreateView,
    TaskSubmissionsView,
    SubmissionReviewView,
    SubmissionAbandonView,
)

urlpatterns = [
    path('feed/', TaskFeedView.as_view(), name='task-feed'),
    path('create/', TaskCreateView.as_view(), name='task-create'),
    path('<uuid:task_id>/', TaskDetailView.as_view(), name='task-detail'),
    path('<uuid:task_id>/close/', TaskCloseView.as_view(), name='task-close'),
    path('<uuid:task_id>/submit/', SubmissionCreateView.as_view(), name='task-submit'),
    path('<uuid:task_id>/submissions/', TaskSubmissionsView.as_view(), name='task-submissions'),
    path('submissions/<uuid:submission_id>/review/', SubmissionReviewView.as_view(), name='submission-review'),
    path('submissions/<uuid:submission_id>/abandon/', SubmissionAbandonView.as_view(), name='submission-abandon'),
]
