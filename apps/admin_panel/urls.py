from django.urls import path
from .views import (
    PendingCompaniesView,
    VerifyCompanyView,
    PendingDITStudentsView,
    VerifyStudentDITView,
    SuspendUserView,
    PlatformAnalyticsView,
)

urlpatterns = [
    path('companies/pending/', PendingCompaniesView.as_view(), name='admin-companies-pending'),
    path('companies/<uuid:company_id>/verify/', VerifyCompanyView.as_view(), name='admin-company-verify'),
    path('students/pending-dit/', PendingDITStudentsView.as_view(), name='admin-students-pending-dit'),
    path('students/<uuid:student_id>/verify-dit/', VerifyStudentDITView.as_view(), name='admin-student-verify-dit'),
    path('users/<uuid:user_id>/suspend/', SuspendUserView.as_view(), name='admin-user-suspend'),
    path('analytics/', PlatformAnalyticsView.as_view(), name='admin-analytics'),
]
