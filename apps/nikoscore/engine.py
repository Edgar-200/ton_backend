"""
TON — NikoScore Engine

THE most critical business logic in the entire system.
Lives ONLY in this file. Never instantiate or call scoring logic from views.

Score structure:
  NikoScore (max 100) = Profile (25) + Activity (25) + Quality (25) + Reliability (25)

All component calculation rules exactly as specified in both documents.
Called via Django signals — never directly from views.
"""

import statistics
import logging
from django.conf import settings
from django.utils import timezone
from django.db import transaction

logger = logging.getLogger(__name__)

COMPONENT_MAX = 25
SCORE_MAX = 100
MIN_REVIEWS_FOR_QUALITY = 3
OUTLIER_WEIGHT = 0.3
OUTLIER_STD_THRESHOLD = 2


class NikoScoreEngine:
    """
    Stateless engine. All methods are class methods — no instance state.
    Entry point: NikoScoreEngine.recalculate(student, trigger, source_id)
    """

    # ─────────────────────────────────────────
    # PRIMARY ENTRY POINT
    # ─────────────────────────────────────────

    @classmethod
    def recalculate(cls, student, trigger: str, source_id=None):
        """
        Main entry point called by Django signals.
        Routes to the correct component recalculation based on trigger type.
        Writes an immutable audit event for every score change.

        Args:
            student:   StudentProfile instance
            trigger:   event type string (matches EventType choices)
            source_id: UUID of the object that caused this event
        """
        try:
            with transaction.atomic():
                ns = cls._get_or_create_nikoscore(student)

                if trigger == 'task_submitted':
                    cls._recalculate_activity(student, ns)
                    cls._recalculate_reliability(student, ns)

                elif trigger == 'task_reviewed':
                    cls._recalculate_quality(student, ns)

                elif trigger == 'submission_abandoned':
                    cls._recalculate_reliability(student, ns)

                elif trigger == 'invitation_responded':
                    cls._recalculate_reliability(student, ns)

                elif trigger in ('profile_completed', 'dit_verified', 'profile_updated'):
                    cls._recalculate_profile(student, ns)

                elif trigger == 'activity_decay':
                    cls._apply_decay(student, ns)

                ns.recalculate_total()
                ns.save()

                cls._check_milestones(student, ns)

        except Exception as e:
            logger.error(f'NikoScoreEngine.recalculate failed for {student.id}: {e}')

    @classmethod
    def recalculate_profile_component(cls, student):
        """Shortcut called from student profile signal."""
        cls.recalculate(student, trigger='profile_updated')

    # ─────────────────────────────────────────
    # COMPONENT: PROFILE (max 25)
    # ─────────────────────────────────────────

    @classmethod
    def _recalculate_profile(cls, student, ns):
        """
        Profile component is a SNAPSHOT of current state — not cumulative.
        If a student removes their photo, the +3 is removed.

        Points:
          DIT enrollment verified    +10  (once only, admin approval)
          Profile photo uploaded     + 3  (photo_url not empty)
          Bio written (50+ words)    + 3  (len(bio.split()) >= 50)
          Course and year filled     + 3  (both fields non-empty)
          Sectors selected (2+)      + 3  (len(sectors) >= 2)
          First task attempted       + 3  (submission count >= 1)
          ─────────────────────────────
          Maximum                     25
        """
        score = 0

        if student.verification_status == 'verified':
            score += 10

        if student.profile_photo_url:
            score += 3

        if student.bio and len(student.bio.split()) >= 50:
            score += 3

        if student.course and student.year_of_study:
            score += 3

        if len(student.sectors) >= 2:
            score += 3

        from apps.tasks.models import Submission
        if Submission.objects.filter(student=student).exists():
            score += 3

        score = min(score, COMPONENT_MAX)

        old = ns.component_profile
        if old != score:
            ns.component_profile = score
            cls._log_event(
                student=student,
                event_type='profile_updated',
                component='profile',
                delta=score - old,
                score_before=old,
                score_after=score,
                reason=f'Profile component recalculated: {score}/25',
            )

    # ─────────────────────────────────────────
    # COMPONENT: ACTIVITY (max 25)
    # ─────────────────────────────────────────

    @classmethod
    def _recalculate_activity(cls, student, ns):
        """
        Activity component rewards volume and consistency.

        Points:
          Tasks attempted (volume)  min(count * 2, 15)   caps at 15
          Active weeks consistency  min(weeks * 2, 10)   caps at 10
          ─────────────────────────────────────────────────────────
          Maximum                                          25

        Decay is handled separately by the daily management command.
        """
        from apps.tasks.models import Submission

        submission_count = Submission.objects.filter(
            student=student
        ).exclude(status='abandoned').count()

        volume_score = min(submission_count * 2, 15)

        active_weeks = cls._count_active_weeks(student)
        consistency_score = min(active_weeks * 2, 10)

        score = min(volume_score + consistency_score, COMPONENT_MAX)

        old = ns.component_activity
        if old != score:
            ns.component_activity = score
            cls._log_event(
                student=student,
                event_type='task_submitted',
                component='activity',
                delta=score - old,
                score_before=old,
                score_after=score,
                reason=f'Activity: {submission_count} tasks, {active_weeks} active weeks → {score}/25',
            )

    @classmethod
    def _count_active_weeks(cls, student):
        """
        Count weeks in which the student had at least one submission or profile update.
        Uses a set of ISO week numbers from submission timestamps.
        """
        from apps.tasks.models import Submission
        submissions = Submission.objects.filter(student=student).values_list('submitted_at', flat=True)
        weeks = set()
        for ts in submissions:
            if ts:
                weeks.add(ts.isocalendar()[:2])  # (year, week) tuple
        return len(weeks)

    # ─────────────────────────────────────────
    # COMPONENT: QUALITY (max 25)
    # ─────────────────────────────────────────

    @classmethod
    def _recalculate_quality(cls, student, ns):
        """
        Quality component — company rating average mapped to 0–25 points.

        Minimum 3 company reviews required before quality score activates.
        Outlier reviews (>2 std dev from mean) are weighted at 0.3x
        to prevent one malicious company from destroying a student's score.

        Mapping: avg 5.0 = 25 pts, avg 1.0 = 5 pts
        Formula: 5 + ((avg - 1) / 4) * 20
        """
        from apps.tasks.models import Submission as Sub

        reviews = (
            Sub.objects
            .filter(student=student, company_score__isnull=False)
            .values_list('company_score', flat=True)
        )
        review_list = list(reviews)

        if len(review_list) < MIN_REVIEWS_FOR_QUALITY:
            # Quality score stays 0 until minimum threshold is met
            score = 0
        else:
            score = cls._weighted_quality_score(review_list)

        old = ns.component_quality
        if old != score:
            ns.component_quality = score
            cls._log_event(
                student=student,
                event_type='task_reviewed',
                component='quality',
                delta=score - old,
                score_before=old,
                score_after=score,
                reason=f'Quality: {len(review_list)} reviews, avg → {score}/25',
            )

    @classmethod
    def _weighted_quality_score(cls, scores: list) -> int:
        """
        Weighted average with outlier detection.
        Outliers (>2 std deviations from mean) weighted at 0.3x.
        Maps result from 1.0–5.0 scale to 5–25 points.
        """
        mean = sum(scores) / len(scores)
        std = statistics.stdev(scores) if len(scores) > 1 else 0

        weighted_sum = 0
        total_weight = 0

        for s in scores:
            weight = OUTLIER_WEIGHT if abs(s - mean) > OUTLIER_STD_THRESHOLD * std else 1.0
            weighted_sum += s * weight
            total_weight += weight

        avg = weighted_sum / total_weight if total_weight > 0 else mean

        # Map 1.0–5.0 → 5–25 points
        mapped = 5 + ((avg - 1) / 4) * 20
        return min(COMPONENT_MAX, max(0, round(mapped)))

    # ─────────────────────────────────────────
    # COMPONENT: RELIABILITY (max 25)
    # ─────────────────────────────────────────

    @classmethod
    def _recalculate_reliability(cls, student, ns):
        """
        Reliability component rewards professional behavior.

        Points:
          Submitted before deadline   +3 per task, max 15
          Profile updated (90 days)   +5 binary
          Responded to invitation     +5 (accept OR decline — responding is what earns)
          Abandoned submission        -2 per abandonment, max penalty -10, floor 0
          ─────────────────────────────────────────────────────────────────────────
          Maximum                      25
        """
        from apps.tasks.models import Submission, Task
        from apps.invitations.models import Invitation
        from django.utils import timezone
        from datetime import timedelta

        # On-time submissions — check each submission individually
        on_time_count = 0
        subs = Submission.objects.filter(student=student).select_related('task')
        for sub in subs:
            if sub.status != 'abandoned' and sub.submitted_at <= sub.task.deadline:
                on_time_count += 1
        on_time_score = min(on_time_count * 3, 15)

        # Profile updated in last 90 days
        recent_update_score = 0
        ninety_days_ago = timezone.now() - timedelta(days=90)
        if student.updated_at >= ninety_days_ago:
            recent_update_score = 5

        # Responded to invitations (accept OR decline — responding earns +5)
        responded_count = Invitation.objects.filter(
            student=student,
            status__in=['accepted', 'declined'],
        ).count()
        invitation_score = 5 if responded_count > 0 else 0

        # Abandoned submission penalty
        abandoned_count = Submission.objects.filter(
            student=student, status='abandoned'
        ).count()
        penalty = min(abandoned_count * 2, 10)  # Max -10

        raw_score = on_time_score + recent_update_score + invitation_score - penalty
        score = min(COMPONENT_MAX, max(0, raw_score))  # Clamp 0–25

        old = ns.component_reliability
        if old != score:
            ns.component_reliability = score
            cls._log_event(
                student=student,
                event_type='task_submitted',
                component='reliability',
                delta=score - old,
                score_before=old,
                score_after=score,
                reason=(
                    f'Reliability: on-time={on_time_count}, '
                    f'invites-responded={responded_count}, '
                    f'abandoned={abandoned_count} → {score}/25'
                ),
            )

    # ─────────────────────────────────────────
    # ACTIVITY DECAY — Daily management command
    # ─────────────────────────────────────────

    @classmethod
    def apply_decay(cls, student):
        """
        Apply inactivity decay to the activity component.
        -1 per week after 30 days inactive. Floor = 0.
        Called by the daily management command at midnight EAT.
        Never called directly from a view or signal.
        """
        try:
            with transaction.atomic():
                ns = cls._get_or_create_nikoscore(student)
                if ns.component_activity <= 0:
                    return

                old = ns.component_activity
                ns.component_activity = max(0, ns.component_activity - settings.NIKOSCORE_INACTIVITY_DECAY_PER_WEEK)
                ns.recalculate_total()
                ns.save()

                cls._log_event(
                    student=student,
                    event_type='activity_decay',
                    component='activity',
                    delta=ns.component_activity - old,
                    score_before=old,
                    score_after=ns.component_activity,
                    reason='Inactivity decay applied (30+ days without activity)',
                )
        except Exception as e:
            logger.error(f'apply_decay failed for {student.id}: {e}')

    # ─────────────────────────────────────────
    # MILESTONE CHECKS
    # ─────────────────────────────────────────

    @classmethod
    def _check_milestones(cls, student, ns):
        """
        Check if student crossed a milestone score (50, 75, 90).
        Triggers a celebration email/SMS notification if so.
        """
        milestones = [50, 75, 90]
        for milestone in milestones:
            if ns.total_score >= milestone:
                # Check if we've already notified for this milestone
                from apps.nikoscore.models import NikoScoreEvent
                already_notified = NikoScoreEvent.objects.filter(
                    student=student,
                    reason__icontains=f'milestone:{milestone}',
                ).exists()
                if not already_notified:
                    try:
                        from apps.notifications.services import NotificationService
                        NotificationService.send_nikoscore_milestone(student.user, milestone, ns.total_score)
                    except Exception:
                        pass

    # ─────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────

    @classmethod
    def _get_or_create_nikoscore(cls, student):
        from apps.nikoscore.models import NikoScore
        ns, _ = NikoScore.objects.get_or_create(student=student)
        return ns

    @classmethod
    def _log_event(cls, student, event_type, component, delta, score_before, score_after, reason, source_id=None):
        """
        Write an immutable audit event.
        Every score change must be logged — no exceptions.
        """
        from apps.nikoscore.models import NikoScoreEvent
        NikoScoreEvent.objects.create(
            student=student,
            event_type=event_type,
            component=component,
            delta=delta,
            score_before=score_before,
            score_after=score_after,
            reason=reason,
            source_id=source_id,
        )



