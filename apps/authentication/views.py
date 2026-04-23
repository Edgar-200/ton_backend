"""
TON — Authentication Views

CRITICAL FLOW:
  1. POST /register/student/ or /register/company/ → creates user + profile, sends OTP
  2. POST /verify-otp/ → verifies OTP, issues JWT tokens (ONLY step that issues tokens)
  3. POST /login/ → for returning verified users
  4. POST /token/refresh/ → rotates refresh token

JWT tokens are NEVER issued at registration. Only after OTP verification.
"""

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken

from .serializers import (
    StudentRegistrationSerializer,
    CompanyRegistrationSerializer,
    OTPVerificationSerializer,
    ResendOTPSerializer,
    LoginSerializer,
    PasswordChangeSerializer,
    ForgotPasswordSerializer,
    ResetPasswordSerializer,
)
from .throttles import RegisterThrottle, LoginThrottle, OTPVerifyThrottle


class StudentRegisterView(APIView):
    """
    POST /api/auth/register/student/
    Creates User + StudentProfile, sends OTP via Africa's Talking SMS.
    Returns user_id and confirmation — NO token issued here.
    """
    permission_classes = [AllowAny]
    throttle_classes = [RegisterThrottle]

    def post(self, request):
        serializer = StudentRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(
            {**result, 'message': 'OTP sent to your registered phone/email.'},
            status=status.HTTP_201_CREATED
        )


class CompanyRegisterView(APIView):
    """
    POST /api/auth/register/company/
    Creates User + Company, sends OTP. Company starts as unverified.
    """
    permission_classes = [AllowAny]
    throttle_classes = [RegisterThrottle]

    def post(self, request):
        serializer = CompanyRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(result, status=status.HTTP_201_CREATED)


class VerifyOTPView(APIView):
    """
    POST /api/auth/verify-otp/
    The ONLY endpoint that issues JWT tokens.
    Blocks after OTP_MAX_ATTEMPTS failed attempts.
    Clears OTP immediately on success.
    """
    permission_classes = [AllowAny]
    throttle_classes = [OTPVerifyThrottle]

    def post(self, request):
        serializer = OTPVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tokens = serializer.save()
        return Response(tokens, status=status.HTTP_200_OK)


class ResendOTPView(APIView):
    """
    POST /api/auth/resend-otp/
    Regenerates OTP and resets attempt counter.
    Rate limited to prevent SMS abuse.
    """
    permission_classes = [AllowAny]
    throttle_classes = [RegisterThrottle]

    def post(self, request):
        serializer = ResendOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(result, status=status.HTTP_200_OK)


class LoginView(APIView):
    """
    POST /api/auth/login/
    For returning verified users. Updates last_active_at on success.
    """
    permission_classes = [AllowAny]
    throttle_classes = [LoginThrottle]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tokens = serializer.save()
        return Response(tokens, status=status.HTTP_200_OK)


class LogoutView(APIView):
    """
    POST /api/auth/logout/
    Blacklists the refresh token — access token expires naturally after 15 min.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({'message': 'Logged out successfully.'}, status=status.HTTP_200_OK)
        except Exception:
            return Response({'error': 'Invalid token.'}, status=status.HTTP_400_BAD_REQUEST)


class TONTokenRefreshView(TokenRefreshView):
    """
    POST /api/auth/token/refresh/
    Standard JWT refresh with last_active_at update.
    """
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            # Update last_active_at on refresh to keep activity score alive
            try:
                from rest_framework_simplejwt.tokens import RefreshToken as RT
                token = RT(request.data.get('refresh'))
                from apps.authentication.models import User
                user = User.objects.get(id=token['user_id'])
                user.touch_last_active()
            except Exception:
                pass  # Never block token refresh due to this
        return response


class PasswordChangeView(APIView):
    """
    POST /api/auth/change-password/
    Authenticated user changes their password.
    Requires current password. Invalidates all existing refresh tokens
    by blacklisting them (handled client-side by logout flow).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PasswordChangeSerializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(result, status=status.HTTP_200_OK)


class ForgotPasswordView(APIView):
    """
    POST /api/auth/forgot-password/
    Sends a password reset email. Always returns 200 to prevent enumeration.
    Rate limited same as registration.
    """
    permission_classes = [AllowAny]
    throttle_classes = [RegisterThrottle]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(result, status=status.HTTP_200_OK)


class ResetPasswordView(APIView):
    """
    POST /api/auth/reset-password/
    Consumes token from email link, sets new password.
    Token is single-use and expires in 30 minutes.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        return Response(result, status=status.HTTP_200_OK)
