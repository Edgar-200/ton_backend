from django.urls import path
from .views import (
    StudentRegisterView,
    CompanyRegisterView,
    VerifyOTPView,
    ResendOTPView,
    LoginView,
    LogoutView,
    TONTokenRefreshView,
    PasswordChangeView,
    ForgotPasswordView,
    ResetPasswordView,
)

urlpatterns = [
    # ── Registration & Verification ──────────────────────────────────────────
    path('register/student/',  StudentRegisterView.as_view(),  name='register-student'),
    path('register/company/',  CompanyRegisterView.as_view(),  name='register-company'),
    path('verify-otp/',        VerifyOTPView.as_view(),        name='verify-otp'),
    path('resend-otp/',        ResendOTPView.as_view(),        name='resend-otp'),

    # ── Login / Logout / Token ────────────────────────────────────────────────
    path('login/',             LoginView.as_view(),            name='login'),
    path('logout/',            LogoutView.as_view(),           name='logout'),
    path('token/refresh/',     TONTokenRefreshView.as_view(),  name='token-refresh'),

    # ── Password Management ───────────────────────────────────────────────────
    path('change-password/',   PasswordChangeView.as_view(),   name='change-password'),
    path('forgot-password/',   ForgotPasswordView.as_view(),   name='forgot-password'),
    path('reset-password/',    ResetPasswordView.as_view(),    name='reset-password'),
]
