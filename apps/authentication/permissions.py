"""
TON — Custom Permission Classes

Role checks live HERE — not inside view logic.
This is enforced globally so no individual view can forget to check.

CRITICAL RULES:
- IsCompany checks BOTH role AND verification_status == 'verified'
- An unverified company must NEVER post tasks, view submissions, or send invitations
- IsAdmin is separate from Django's is_staff — uses role field
"""

from rest_framework.permissions import BasePermission


class IsStudent(BasePermission):
    """
    Grants access to authenticated users with role='student'.
    Does NOT require DIT verification — some endpoints are available to unverified students.
    """
    message = 'Student access required.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == 'student'
        )


class IsVerifiedStudent(BasePermission):
    """
    Grants access only to students whose DIT enrollment has been verified by admin.
    Required for: submission posting, invitation responses.
    """
    message = 'DIT-verified student access required.'

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated and request.user.role == 'student'):
            return False
        try:
            return request.user.student_profile.verification_status == 'verified'
        except Exception:
            return False


class IsCompany(BasePermission):
    """
    Grants access to authenticated, VERIFIED companies.
    Unverified companies receive 403 on ALL write operations.

    Enforced at permission class — not in individual view logic.
    """
    message = 'Verified company access required.'

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated and request.user.role == 'company'):
            return False
        try:
            return request.user.company_profile.verification_status == 'verified'
        except Exception:
            return False


class IsUnverifiedCompany(BasePermission):
    """Used for read-only company endpoints accessible before verification (e.g., profile view)."""
    message = 'Company access required.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == 'company'
        )


class IsAdmin(BasePermission):
    """
    Platform admin — full access. Uses role field, not Django's is_staff alone.
    Every admin action is logged with timestamp and reason.
    """
    message = 'Admin access required.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == 'admin'
        )


class IsOwnerOrAdmin(BasePermission):
    """Object-level: user can only access their own resource, or admin can access all."""
    message = 'Access restricted to owner.'

    def has_object_permission(self, request, view, obj):
        if request.user.role == 'admin':
            return True
        # Works for models where obj.user == request.user
        if hasattr(obj, 'user'):
            return obj.user == request.user
        if hasattr(obj, 'student'):
            return obj.student.user == request.user
        return False
