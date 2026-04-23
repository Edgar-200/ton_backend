from django.urls import path
from .views import (
    CompanyProfileView,
    CompanyDashboardView,
    WatchlistView,
    WatchlistAddView,
    WatchlistRemoveView,
)

urlpatterns = [
    path('profile/', CompanyProfileView.as_view(), name='company-profile'),
    path('dashboard/', CompanyDashboardView.as_view(), name='company-dashboard'),
    path('watchlist/', WatchlistView.as_view(), name='watchlist'),
    path('watchlist/add/', WatchlistAddView.as_view(), name='watchlist-add'),
    path('watchlist/remove/<uuid:entry_id>/', WatchlistRemoveView.as_view(), name='watchlist-remove'),
]
