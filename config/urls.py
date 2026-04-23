"""
TON — Root URL Configuration
All API routes under /api/
Root / returns a health-check JSON response so visiting the server
in a browser or via curl shows something useful instead of a 404.
"""

from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from django.utils import timezone


def health_check(request):
    return JsonResponse({
        'service': 'TON — Talent Observable Network',
        'status': 'running',
        'version': '1.0.0',
        'timestamp': timezone.now().isoformat(),
        'endpoints': {
            'auth':        '/api/auth/',
            'students':    '/api/students/',
            'companies':   '/api/companies/',
            'tasks':       '/api/tasks/',
            'nikoscore':   '/api/nikoscore/',
            'invitations': '/api/invitations/',
            'admin':       '/api/admin/',
            'django_admin':'/django-admin/',
        },
    })


urlpatterns = [
    # Health check — visible at root URL
    path('', health_check, name='health-check'),

    # Django built-in admin
    path('django-admin/', admin.site.urls),

    # API routes
    path('api/auth/',        include('apps.authentication.urls')),
    path('api/students/',    include('apps.students.urls')),
    path('api/companies/',   include('apps.companies.urls')),
    path('api/tasks/',       include('apps.tasks.urls')),
    path('api/nikoscore/',   include('apps.nikoscore.urls')),
    path('api/invitations/', include('apps.invitations.urls')),
    path('api/admin/',       include('apps.admin_panel.urls')),
]
