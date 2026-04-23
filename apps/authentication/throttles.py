"""
TON — Custom Throttle Classes

Rate limits per endpoint as specified in the system design:
  - Register: 5 per IP per hour
  - OTP verify: 5 per user (enforced in serializer too)
  - Login: 10 per IP per 15 minutes
  - Task submit: 3 per student per task per hour
  - Invitation send: 20 per company per day
"""

from rest_framework.throttling import AnonRateThrottle, UserRateThrottle, SimpleRateThrottle


class RegisterThrottle(AnonRateThrottle):
    """5 registration attempts per IP per hour."""
    scope = 'register'
    rate = '5/hour'


class LoginThrottle(AnonRateThrottle):
    """10 login attempts per IP per 15 minutes."""
    scope = 'login'
    rate = '10/15min'


class OTPVerifyThrottle(AnonRateThrottle):
    """5 OTP verification attempts per IP per hour. Per-user limit enforced in serializer."""
    scope = 'otp_verify'
    rate = '5/hour'


class TaskSubmitThrottle(UserRateThrottle):
    """3 submission attempts per user per hour per task."""
    scope = 'task_submit'
    rate = '3/hour'


class InvitationSendThrottle(UserRateThrottle):
    """20 invitations per company per day — prevents invitation spam."""
    scope = 'invitation_send'
    rate = '20/day'
