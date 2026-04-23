"""
TON — Notification Service

Two delivery channels for OTP:
  Email → Resend API       GUARANTEED — always sent, no conditions
  SMS   → Africa's Talking ADDITIONAL — sent only when user.phone is set

All other notifications (DIT verified, invitation sent, etc.) are email-only
unless specified otherwise.

CRITICAL DELIVERY RULE:
  send_registration_otp() ALWAYS sends to email first.
  If that fails it is logged but never raises — the API response still succeeds.
  SMS is a bonus channel; its failure is silent.

TANZANIA PHONE FORMAT: E.164  +255XXXXXXXXX
  Strip leading 0, add +255. Already normalised before storing on User.phone.

NOTIFICATION TRIGGER MAP:
  User registers            → OTP via email (always) + SMS (if phone set)
  OTP resend requested      → same as above
  Student DIT verified      → Congratulations email + SMS
  Student DIT rejected      → Rejection email only
  Company verified          → Welcome email only
  Company rejected          → Rejection email only
  Invitation sent           → Email + SMS to student
  Invitation accepted       → Email to company (with student contact)
  Invitation declined       → Email to company
  NikoScore milestone       → Celebration email (50, 75, 90)

DO NOT email students every time a task is posted — weekly digest is Month 2.
"""

import logging
import africastalking
import resend
from django.conf import settings

logger = logging.getLogger(__name__)

# ── Service initialisation ────────────────────────────────────────────────────
# Both services initialise at module load, once per process.

africastalking.initialize(
    username=settings.AT_USERNAME,
    api_key=settings.AT_API_KEY,
)
_sms_service = africastalking.SMS

resend.api_key = settings.RESEND_API_KEY


# ── Low-level helpers ─────────────────────────────────────────────────────────

def _send_email(to: str, subject: str, html: str) -> bool:
    """
    Send transactional email via Resend.
    Never raises — failures are logged and False is returned.
    """
    try:
        resend.Emails.send({
            'from': settings.RESEND_FROM_EMAIL,
            'to': [to],
            'subject': subject,
            'html': html,
        })
        logger.info(f'[email] sent  to={to}  subject={subject!r}')
        return True
    except Exception as exc:
        logger.error(f'[email] FAILED  to={to}  subject={subject!r}  err={exc}')
        return False


def _send_sms(phone: str, message: str) -> bool:
    """
    Send SMS via Africa's Talking.
    phone must already be in E.164 format (+255XXXXXXXXX).
    Never raises — failures are logged and False is returned.
    Sender ID 'TON' must be registered with Africa's Talking before going live.
    """
    try:
        response = _sms_service.send(
            message,
            [phone],
            sender_id=settings.AT_SENDER_ID,
        )
        logger.info(f'[sms] sent  to={phone}  response={response}')
        return True
    except Exception as exc:
        logger.error(f'[sms] FAILED  to={phone}  err={exc}')
        return False


# ── Notification service ──────────────────────────────────────────────────────

class NotificationService:
    """
    Stateless dispatcher. All methods are @classmethod — no instance needed.
    """

    # ── OTP / Registration ────────────────────────────────────────────────────

    @classmethod
    def send_registration_otp(cls, user, otp: str) -> dict:
        """
        Send the verification OTP after registration or on resend request.

        Delivery strategy:
          1. Email is sent FIRST and is the guaranteed channel.
          2. SMS is sent ADDITIONALLY if user.phone is set.

        Returns a dict describing which channels were used, so the
        view can include this in the API response and the frontend
        can tell the user exactly where to look for their code.

        Example return value:
          { 'email': True, 'sms': True,  'email_address': 'a@b.com', 'phone': '+255...' }
          { 'email': True, 'sms': False, 'email_address': 'a@b.com', 'phone': None }
        """
        subject = 'Your TON Verification Code'
        html = _otp_email_html(otp, user.email)

        # Step 1 — Email (always, unconditional)
        email_sent = _send_email(user.email, subject, html)

        # Step 2 — SMS (only if phone is stored)
        sms_sent = False
        if user.phone:
            sms_body = (
                f'TON: Your verification code is {otp}. '
                f'Valid for {settings.OTP_EXPIRY_MINUTES} minutes. '
                f'Do not share this code.'
            )
            sms_sent = _send_sms(user.phone, sms_body)

        return {
            'email': email_sent,
            'sms': sms_sent,
            'email_address': user.email,
            'phone': user.phone or None,
        }

    # ── DIT Verification ──────────────────────────────────────────────────────

    @classmethod
    def send_dit_verified(cls, user):
        """Student DIT enrollment approved by admin. Email + SMS."""
        name = user.student_profile.full_name
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto">
          <h2 style="color:#0A0A0F">DIT Verification Approved ✅</h2>
          <p>Hi {name},</p>
          <p>Your DIT enrollment has been verified by the TON team.
             Your <strong>NikoScore profile component</strong> is now active.</p>
          <p>Start attempting tasks to build your proof trail and attract company attention.</p>
          <p style="margin-top:24px">
            <a href="{_fe()}/dashboard"
               style="background:#00FF87;color:#0A0A0F;padding:12px 24px;
                      border-radius:6px;text-decoration:none;font-weight:bold">
              Go to your dashboard →
            </a>
          </p>
        </div>
        """
        _send_email(user.email, 'DIT Verification Approved — TON', html)

        if user.phone:
            _send_sms(user.phone, f'TON: Your DIT enrollment is verified! Log in to start attempting tasks and build your NikoScore.')

    @classmethod
    def send_dit_rejected(cls, user, reason: str):
        """Student DIT verification rejected by admin. Email only."""
        name = user.student_profile.full_name
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto">
          <h2 style="color:#0A0A0F">DIT Verification — Action Required</h2>
          <p>Hi {name},</p>
          <p>We could not verify your DIT enrollment document.</p>
          <p><strong>Reason:</strong> {reason}</p>
          <p>Please upload a clearer image of your DIT student ID card and try again.
             Make sure all text is legible and the document is not expired.</p>
          <p style="margin-top:24px">
            <a href="{_fe()}/profile/verify"
               style="background:#FFB800;color:#0A0A0F;padding:12px 24px;
                      border-radius:6px;text-decoration:none;font-weight:bold">
              Resubmit your document →
            </a>
          </p>
        </div>
        """
        _send_email(user.email, 'DIT Verification — Please Resubmit | TON', html)

    # ── Company Verification ──────────────────────────────────────────────────

    @classmethod
    def send_company_verified(cls, user):
        """Company approved by admin. Email only."""
        name = user.company_profile.company_name
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto">
          <h2 style="color:#0A0A0F">Welcome to TON, {name}! 🎉</h2>
          <p>Your company has been verified. You can now:</p>
          <ul>
            <li>Post tasks for DIT students</li>
            <li>Review student submissions privately</li>
            <li>Watch promising students and send invitations</li>
          </ul>
          <p><strong>Next step:</strong> Post your first task to start discovering talent.</p>
          <p style="margin-top:24px">
            <a href="{_fe()}/company/tasks/create"
               style="background:#00FF87;color:#0A0A0F;padding:12px 24px;
                      border-radius:6px;text-decoration:none;font-weight:bold">
              Post your first task →
            </a>
          </p>
        </div>
        """
        _send_email(user.email, 'Company Verified — Post Your First Task | TON', html)

    @classmethod
    def send_company_rejected(cls, user, reason: str):
        """Company verification rejected. Email only."""
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto">
          <h2 style="color:#0A0A0F">Company Verification — Action Required</h2>
          <p>We could not verify your company at this time.</p>
          <p><strong>Reason:</strong> {reason}</p>
          <p>Please review the information you submitted and contact us if you believe
             this is an error.</p>
        </div>
        """
        _send_email(user.email, 'Company Verification — Please Review | TON', html)

    # ── Submissions ───────────────────────────────────────────────────────────

    @classmethod
    def send_new_submission_received(cls, submission):
        """Notify company of a new submission on their task. Email only."""
        company = submission.task.company
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto">
          <h2 style="color:#0A0A0F">New Submission on "{submission.task.title}"</h2>
          <p>A student has submitted work on your task.</p>
          <p>Total submissions so far: <strong>{submission.task.submissions_count}</strong></p>
          <p style="margin-top:24px">
            <a href="{_fe()}/company/tasks/{submission.task.id}/submissions"
               style="background:#00FF87;color:#0A0A0F;padding:12px 24px;
                      border-radius:6px;text-decoration:none;font-weight:bold">
              Review submissions →
            </a>
          </p>
        </div>
        """
        _send_email(company.user.email, f'New Submission — {submission.task.title} | TON', html)

    # ── Invitations ───────────────────────────────────────────────────────────

    @classmethod
    def send_invitation_received(cls, invitation):
        """Notify student of a new invitation. Email + SMS."""
        student = invitation.student
        company = invitation.company
        inv_type = invitation.get_invitation_type_display()

        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto">
          <h2 style="color:#0A0A0F">You have a new invitation! 🎉</h2>
          <p>Hi {student.full_name},</p>
          <p><strong>{company.company_name}</strong> has sent you a
             <strong>{inv_type}</strong> invitation.</p>
          <blockquote style="border-left:4px solid #00FF87;padding-left:16px;color:#555">
            {invitation.message}
          </blockquote>
          <p style="color:#999;font-size:13px">
            This invitation expires in 14 days. Responding — even declining —
            earns you +5 reliability points on your NikoScore.
          </p>
          <p style="margin-top:24px">
            <a href="{_fe()}/invitations/{invitation.id}"
               style="background:#00FF87;color:#0A0A0F;padding:12px 24px;
                      border-radius:6px;text-decoration:none;font-weight:bold">
              View and respond →
            </a>
          </p>
        </div>
        """
        _send_email(
            student.user.email,
            f'Invitation from {company.company_name} — TON',
            html,
        )

        if student.user.phone:
            _send_sms(
                student.user.phone,
                f'TON: {company.company_name} sent you a {inv_type} invitation. '
                f'Log in to respond before it expires.',
            )

    @classmethod
    def send_invitation_accepted(cls, invitation):
        """
        Notify company that student accepted.
        Student email is included — contact_released=True is confirmed
        inside the invitation model before this is called.
        """
        company = invitation.company
        student = invitation.student

        contact_block = ''
        if invitation.contact_released:
            contact_block = f"""
            <p style="background:#f0fff8;border:1px solid #00FF87;
                      padding:16px;border-radius:6px">
              <strong>Student contact:</strong><br>
              Email: {student.user.email}
              {'<br>Phone: ' + student.user.phone if student.user.phone else ''}
            </p>
            """

        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto">
          <h2 style="color:#0A0A0F">{student.full_name} accepted your invitation! ✅</h2>
          <p>{student.full_name} has accepted your
             {invitation.get_invitation_type_display()} invitation.</p>
          {contact_block}
          <p style="margin-top:24px">
            <a href="{_fe()}/company/invitations"
               style="background:#00FF87;color:#0A0A0F;padding:12px 24px;
                      border-radius:6px;text-decoration:none;font-weight:bold">
              View invitation →
            </a>
          </p>
        </div>
        """
        _send_email(
            company.user.email,
            f'{student.full_name} Accepted Your Invitation — TON',
            html,
        )

    @classmethod
    def send_invitation_declined(cls, invitation):
        """Notify company that student declined. No contact details shared."""
        company = invitation.company
        student = invitation.student

        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto">
          <h2 style="color:#0A0A0F">{student.full_name} declined your invitation</h2>
          <p>{student.full_name} has declined your
             {invitation.get_invitation_type_display()} invitation.</p>
          <p>You can browse other students on your watchlist.</p>
          <p style="margin-top:24px">
            <a href="{_fe()}/company/watchlist"
               style="background:#FFB800;color:#0A0A0F;padding:12px 24px;
                      border-radius:6px;text-decoration:none;font-weight:bold">
              Browse watchlist →
            </a>
          </p>
        </div>
        """
        _send_email(company.user.email, 'Invitation Declined — TON', html)

    # ── NikoScore Milestones ──────────────────────────────────────────────────

    @classmethod
    def send_nikoscore_milestone(cls, user, milestone: int, current_score: int):
        """Celebrate score milestones (50, 75, 90). Email only."""
        labels = {50: 'halfway there', 75: 'a top performer', 90: 'elite talent'}
        label = labels.get(milestone, 'a new milestone')
        name = user.student_profile.full_name

        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto">
          <h2 style="color:#0A0A0F">🎉 NikoScore {milestone} Reached!</h2>
          <p>Hi {name},</p>
          <p>Your NikoScore has reached <strong>{current_score}/100</strong>
             — you are {label}!</p>
          <p>Companies browsing TON can see your score. Keep building your proof trail.</p>
          <p style="margin-top:24px">
            <a href="{_fe()}/profile"
               style="background:#00FF87;color:#0A0A0F;padding:12px 24px;
                      border-radius:6px;text-decoration:none;font-weight:bold">
              View your profile →
            </a>
          </p>
        </div>
        """
        _send_email(user.email, f'🎉 NikoScore {milestone} Reached — TON', html)


    # ── Password Management ───────────────────────────────────────────────────

    @classmethod
    def send_password_reset_link(cls, user, token: str):
        """
        Send a password reset link to the user's email.
        Link format: {FRONTEND_URL}/reset-password?token={token}
        Token expires in PASSWORD_RESET_EXPIRY_MINUTES (default 30).
        """
        from django.conf import settings
        expiry = getattr(settings, 'PASSWORD_RESET_EXPIRY_MINUTES', 30)
        reset_url = f'{_fe()}/reset-password?token={token}'

        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head><meta charset="UTF-8"></head>
        <body style="margin:0;padding:0;background:#f5f5f5;font-family:Arial,sans-serif">
          <table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f5f5;padding:40px 20px">
            <tr><td align="center">
              <table width="560" cellpadding="0" cellspacing="0"
                     style="background:#ffffff;border-radius:12px;overflow:hidden;
                            box-shadow:0 2px 8px rgba(0,0,0,0.08)">
                <tr>
                  <td style="background:#0A0A0F;padding:28px 40px">
                    <span style="color:#00FF87;font-size:22px;font-weight:bold;letter-spacing:2px">TON</span>
                    <span style="color:#555;font-size:13px;margin-left:8px">Talent Observable Network</span>
                  </td>
                </tr>
                <tr>
                  <td style="padding:40px">
                    <h2 style="margin:0 0 16px;color:#0A0A0F;font-size:20px">Reset your password</h2>
                    <p style="color:#444;line-height:1.6;margin:0 0 24px">
                      We received a request to reset the password for your TON account.
                      Click the button below to set a new password.
                      This link expires in <strong>{expiry} minutes</strong>.
                    </p>
                    <p style="text-align:center;margin:0 0 32px">
                      <a href="{reset_url}"
                         style="background:#00FF87;color:#0A0A0F;padding:14px 32px;
                                border-radius:8px;text-decoration:none;font-weight:bold;
                                font-size:16px;display:inline-block">
                        Reset my password
                      </a>
                    </p>
                    <p style="color:#888;font-size:13px;margin:0 0 8px">
                      Or copy and paste this link into your browser:
                    </p>
                    <p style="color:#555;font-size:12px;word-break:break-all;
                              background:#f9f9f9;padding:12px;border-radius:6px">
                      {reset_url}
                    </p>
                    <p style="color:#999;font-size:12px;margin:24px 0 0;
                              border-top:1px solid #f0f0f0;padding-top:16px;line-height:1.6">
                      🔒 If you did not request a password reset, you can safely ignore this email.
                      Your password will not change. TON staff will never ask for your password.
                    </p>
                  </td>
                </tr>
                <tr>
                  <td style="background:#f9f9f9;padding:20px 40px;
                             border-top:1px solid #f0f0f0;text-align:center">
                    <p style="color:#bbb;font-size:12px;margin:0">
                      © 2026 TON — Talent Observable Network, Dar es Salaam, Tanzania
                    </p>
                  </td>
                </tr>
              </table>
            </td></tr>
          </table>
        </body>
        </html>
        """
        _send_email(user.email, 'Reset Your TON Password', html)

    @classmethod
    def send_password_changed(cls, user):
        """
        Security alert email sent after any password change or reset.
        Warns the user to contact support if they didn't initiate the change.
        """
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:560px;margin:0 auto">
          <div style="background:#0A0A0F;padding:24px 32px">
            <span style="color:#00FF87;font-size:20px;font-weight:bold;letter-spacing:2px">TON</span>
          </div>
          <div style="padding:32px;background:#fff">
            <h2 style="color:#0A0A0F;margin:0 0 16px">Your password was changed</h2>
            <p style="color:#444;line-height:1.6">
              The password for your TON account (<strong>{user.email}</strong>)
              was successfully changed.
            </p>
            <p style="color:#444;line-height:1.6">
              If you made this change, no further action is needed.
            </p>
            <p style="background:#fff8e1;border-left:4px solid #FFB800;
                      padding:12px 16px;color:#444;line-height:1.6">
              <strong>⚠ If you did not change your password</strong>, your account may be compromised.
              Please contact us immediately at <a href="mailto:support@ton.co.tz">support@ton.co.tz</a>.
            </p>
          </div>
          <div style="background:#f9f9f9;padding:16px 32px;text-align:center">
            <p style="color:#bbb;font-size:12px;margin:0">
              © 2026 TON — Dar es Salaam, Tanzania
            </p>
          </div>
        </div>
        """
        _send_email(user.email, 'Your TON Password Was Changed', html)


# ── Email templates ───────────────────────────────────────────────────────────

def _otp_email_html(otp: str, email: str) -> str:
    """Branded OTP email template. Large code display with expiry and security notice."""
    from django.conf import settings
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
    <body style="margin:0;padding:0;background:#f5f5f5;font-family:Arial,sans-serif">
      <table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f5f5;padding:40px 20px">
        <tr><td align="center">
          <table width="560" cellpadding="0" cellspacing="0"
                 style="background:#ffffff;border-radius:12px;overflow:hidden;
                        box-shadow:0 2px 8px rgba(0,0,0,0.08)">
            <tr>
              <td style="background:#0A0A0F;padding:28px 40px">
                <span style="color:#00FF87;font-size:22px;font-weight:bold;letter-spacing:2px">TON</span>
                <span style="color:#555;font-size:13px;margin-left:8px">Talent Observable Network</span>
              </td>
            </tr>
            <tr>
              <td style="padding:40px">
                <h2 style="margin:0 0 16px;color:#0A0A0F;font-size:20px">Verify your email address</h2>
                <p style="color:#444;line-height:1.6;margin:0 0 32px">
                  Enter this 6-digit code to complete your registration.
                  The code expires in <strong>{settings.OTP_EXPIRY_MINUTES} minutes</strong>.
                </p>
                <div style="background:#f0fff8;border:2px solid #00FF87;border-radius:10px;
                            padding:28px;text-align:center;margin-bottom:32px">
                  <span style="font-size:42px;font-weight:bold;letter-spacing:12px;
                               color:#0A0A0F;font-family:'Courier New',monospace">
                    {otp}
                  </span>
                  <p style="margin:12px 0 0;color:#888;font-size:13px">
                    Enter this code in the TON app
                  </p>
                </div>
                <p style="color:#555;font-size:14px;margin:0 0 8px">
                  This code was sent to: <strong>{email}</strong>
                </p>
                <p style="color:#999;font-size:12px;margin:24px 0 0;
                          border-top:1px solid #f0f0f0;padding-top:16px;line-height:1.6">
                  🔒 Never share this code with anyone.
                  TON staff will never ask for it.
                  If you did not create a TON account, ignore this email.
                </p>
              </td>
            </tr>
            <tr>
              <td style="background:#f9f9f9;padding:20px 40px;
                         border-top:1px solid #f0f0f0;text-align:center">
                <p style="color:#bbb;font-size:12px;margin:0">
                  © 2026 TON — Talent Observable Network, Dar es Salaam, Tanzania
                </p>
              </td>
            </tr>
          </table>
        </td></tr>
      </table>
    </body>
    </html>
    """


def _fe() -> str:
    """Return the configured frontend base URL."""
    from django.conf import settings
    return getattr(settings, 'FRONTEND_URL', 'https://ton.co.tz')
