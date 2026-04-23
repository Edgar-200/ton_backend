from django.urls import path
from .views import MyNikoScoreView, StudentNikoScoreCompanyView

urlpatterns = [
    path('my-score/', MyNikoScoreView.as_view(), name='my-nikoscore'),
    path('student/<uuid:student_id>/', StudentNikoScoreCompanyView.as_view(), name='student-nikoscore-company'),
]
