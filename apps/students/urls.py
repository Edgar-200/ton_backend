from django.urls import path
from .views import (
    StudentProfileView,
    DITVerificationView,
    StudentPublicProfileView,
    StudentDashboardView,
    StudentSubmissionListView,
)

urlpatterns = [
    path('profile/',                              StudentProfileView.as_view(),         name='student-profile'),
    path('verify-dit/',                           DITVerificationView.as_view(),        name='student-verify-dit'),
    path('public-profile/<uuid:student_id>/',     StudentPublicProfileView.as_view(),   name='student-public-profile'),
    path('dashboard/',                            StudentDashboardView.as_view(),       name='student-dashboard'),
    path('submissions/',                          StudentSubmissionListView.as_view(),  name='student-submissions'),
]
