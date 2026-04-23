"""
TON — Authentication Test Suite

Tests the most security-critical flows:
  - Registration does NOT issue tokens
  - OTP verification DOES issue tokens
  - OTP is cleared after successful verification
  - Failed OTP increments attempt counter and locks after 5
  - Unverified user cannot log in
  - Suspended user cannot log in
"""

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient
from rest_framework import status

from apps.authentication.models import User
from unittest.mock import patch


class StudentRegistrationTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('register-student')

    def test_registration_returns_201_without_token(self):
        payload = {
            'email': 'student@dit.ac.tz',
            'password': 'SecurePass123',
            'full_name': 'Amina Hassan',
            'dit_student_id': 'DIT/2024/001',
            'course': 'ict',
            'year_of_study': 2,
        }
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # CRITICAL: No token issued at registration
        self.assertNotIn('access', response.data)
        self.assertNotIn('refresh', response.data)
        self.assertIn('user_id', response.data)

    def test_duplicate_email_returns_400(self):
        User.objects.create_user(email='student@dit.ac.tz', password='pass', role='student')
        payload = {
            'email': 'student@dit.ac.tz',
            'password': 'SecurePass123',
            'full_name': 'Other Student',
            'dit_student_id': 'DIT/2024/002',
            'course': 'ict',
            'year_of_study': 1,
        }
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_required_field_returns_400(self):
        payload = {'email': 'student2@dit.ac.tz', 'password': 'pass123'}
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class OTPVerificationTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('verify-otp')

        self.user = User.objects.create_user(
            email='test@dit.ac.tz',
            password='testpass123',
            role='student',
        )
        self.otp_plain = '123456'
        self.user.otp_code = make_password(self.otp_plain)
        self.user.otp_expires_at = timezone.now() + timedelta(minutes=10)
        self.user.otp_attempts = 0
        self.user.save()

    def test_correct_otp_issues_tokens(self):
        response = self.client.post(self.url, {
            'email': 'test@dit.ac.tz',
            'code': self.otp_plain,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertIn('role', response.data)

    def test_correct_otp_clears_otp_code(self):
        self.client.post(self.url, {
            'email': 'test@dit.ac.tz',
            'code': self.otp_plain,
        }, format='json')
        self.user.refresh_from_db()
        self.assertIsNone(self.user.otp_code)
        self.assertIsNone(self.user.otp_expires_at)
        self.assertEqual(self.user.otp_attempts, 0)
        self.assertTrue(self.user.is_verified)

    def test_wrong_otp_increments_attempt_counter(self):
        self.client.post(self.url, {'email': 'test@dit.ac.tz', 'code': '000000'}, format='json')
        self.user.refresh_from_db()
        self.assertEqual(self.user.otp_attempts, 1)

    def test_locked_after_five_failed_attempts(self):
        self.user.otp_attempts = 5
        self.user.save(update_fields=['otp_attempts'])
        response = self.client.post(self.url, {
            'email': 'test@dit.ac.tz',
            'code': self.otp_plain,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_expired_otp_returns_400(self):
        self.user.otp_expires_at = timezone.now() - timedelta(minutes=1)
        self.user.save(update_fields=['otp_expires_at'])
        response = self.client.post(self.url, {
            'email': 'test@dit.ac.tz',
            'code': self.otp_plain,
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class LoginTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('login')
        self.user = User.objects.create_user(
            email='login@dit.ac.tz',
            password='correctpass',
            role='student',
        )
        self.user.is_verified = True
        self.user.save(update_fields=['is_verified'])

    def test_verified_user_can_login(self):
        response = self.client.post(self.url, {
            'email': 'login@dit.ac.tz',
            'password': 'correctpass',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)

    def test_unverified_user_cannot_login(self):
        self.user.is_verified = False
        self.user.save(update_fields=['is_verified'])
        response = self.client.post(self.url, {
            'email': 'login@dit.ac.tz',
            'password': 'correctpass',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_suspended_user_cannot_login(self):
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        response = self.client.post(self.url, {
            'email': 'login@dit.ac.tz',
            'password': 'correctpass',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_wrong_password_returns_400(self):
        response = self.client.post(self.url, {
            'email': 'login@dit.ac.tz',
            'password': 'wrongpassword',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class RegistrationOTPEmailDeliveryTest(TestCase):
    """
    Tests the full registration → OTP email → verify flow.
    Confirms email is always sent regardless of phone presence,
    and that the response tells the caller exactly where the code was sent.
    """

    def setUp(self):
        self.client = APIClient()
        self.register_url = reverse('register-student')
        self.verify_url = reverse('verify-otp')

    @patch('apps.notifications.services._send_email', return_value=True)
    @patch('apps.notifications.services._send_sms', return_value=False)
    def test_registration_always_sends_email(self, mock_sms, mock_email):
        """Email is sent even when no phone is provided."""
        response = self.client.post(self.register_url, {
            'email': 'nophone@dit.ac.tz',
            'password': 'SecurePass1',
            'full_name': 'No Phone Student',
            'dit_student_id': 'DIT/NP/001',
            'course': 'ict',
            'year_of_study': 1,
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(mock_email.called)
        self.assertFalse(mock_sms.called)

        data = response.data
        self.assertIn('delivery_channels', data)
        self.assertTrue(data['delivery_channels']['email'])
        self.assertFalse(data['delivery_channels']['sms'])
        self.assertIsNone(data['delivery_channels']['phone'])
        # No token issued at registration
        self.assertNotIn('access', data)

    @patch('apps.notifications.services._send_email', return_value=True)
    @patch('apps.notifications.services._send_sms', return_value=True)
    def test_registration_sends_sms_when_phone_provided(self, mock_sms, mock_email):
        """Both email and SMS are sent when phone is provided."""
        response = self.client.post(self.register_url, {
            'email': 'withphone@dit.ac.tz',
            'password': 'SecurePass1',
            'full_name': 'Phone Student',
            'dit_student_id': 'DIT/WP/001',
            'course': 'ict',
            'year_of_study': 2,
            'phone': '0712345678',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(mock_email.called)
        self.assertTrue(mock_sms.called)

        data = response.data
        self.assertTrue(data['delivery_channels']['email'])
        self.assertTrue(data['delivery_channels']['sms'])
        self.assertEqual(data['delivery_channels']['phone'], '+255712345678')

    @patch('apps.notifications.services._send_email', return_value=True)
    @patch('apps.notifications.services._send_sms', return_value=True)
    def test_full_registration_verify_flow_issues_token(self, mock_sms, mock_email):
        """
        End-to-end: register → OTP intercepted → verify → receive JWT tokens.
        Confirms tokens are issued ONLY after verification.
        """
        from unittest.mock import patch as _patch
        import apps.authentication.serializers as auth_ser

        captured_otp = {}

        original_generate = auth_ser._generate_otp
        def capturing_generate():
            otp = original_generate()
            captured_otp['value'] = otp
            return otp

        with _patch.object(auth_ser, '_generate_otp', side_effect=capturing_generate):
            reg = self.client.post(self.register_url, {
                'email': 'flow@dit.ac.tz',
                'password': 'FlowPass99',
                'full_name': 'Flow Test Student',
                'dit_student_id': 'DIT/FLOW/001',
                'course': 'ict',
                'year_of_study': 3,
            }, format='json')

        self.assertEqual(reg.status_code, status.HTTP_201_CREATED)
        self.assertNotIn('access', reg.data)   # No token yet
        self.assertIn('user_id', reg.data)

        # Verify with the captured OTP
        verify = self.client.post(self.verify_url, {
            'email': 'flow@dit.ac.tz',
            'code': captured_otp['value'],
        }, format='json')

        self.assertEqual(verify.status_code, status.HTTP_200_OK)
        self.assertIn('access', verify.data)
        self.assertIn('refresh', verify.data)
        self.assertEqual(verify.data['role'], 'student')
        self.assertIn('message', verify.data)

        # OTP must be cleared in DB
        user = User.objects.get(email='flow@dit.ac.tz')
        self.assertIsNone(user.otp_code)
        self.assertTrue(user.is_verified)

    def test_invalid_phone_format_rejected(self):
        """Phone numbers that are not valid Tanzanian numbers are rejected."""
        response = self.client.post(self.register_url, {
            'email': 'badphone@dit.ac.tz',
            'password': 'SecurePass1',
            'full_name': 'Bad Phone Student',
            'dit_student_id': 'DIT/BP/001',
            'course': 'ict',
            'year_of_study': 1,
            'phone': '12345',  # Too short and wrong format
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('phone', response.data)

    def test_already_verified_account_cannot_reverify(self):
        """Verified account trying to verify again gets a clear error."""
        user = User.objects.create_user(
            email='already@dit.ac.tz', password='pass', role='student',
        )
        user.is_verified = True
        user.save(update_fields=['is_verified'])

        response = self.client.post(self.verify_url, {
            'email': 'already@dit.ac.tz',
            'code': '123456',
        }, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already verified', str(response.data).lower())
