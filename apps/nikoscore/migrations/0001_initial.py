"""
TON — NikoScore Initial Migration
Creates nikoscores (cache) and nikoscore_events (immutable audit log).

nikoscore_events uses PROTECT on student FK — audit log must survive
student soft-delete. Records are never updated or deleted.
"""

import uuid
import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('students', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='NikoScore',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('student', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='nikoscore',
                    to='students.studentprofile',
                )),
                ('total_score', models.IntegerField(
                    default=0,
                    validators=[
                        django.core.validators.MinValueValidator(0),
                        django.core.validators.MaxValueValidator(100),
                    ],
                )),
                ('component_profile', models.IntegerField(
                    default=0,
                    validators=[
                        django.core.validators.MinValueValidator(0),
                        django.core.validators.MaxValueValidator(25),
                    ],
                )),
                ('component_activity', models.IntegerField(
                    default=0,
                    validators=[
                        django.core.validators.MinValueValidator(0),
                        django.core.validators.MaxValueValidator(25),
                    ],
                )),
                ('component_quality', models.IntegerField(
                    default=0,
                    validators=[
                        django.core.validators.MinValueValidator(0),
                        django.core.validators.MaxValueValidator(25),
                    ],
                )),
                ('component_reliability', models.IntegerField(
                    default=0,
                    validators=[
                        django.core.validators.MinValueValidator(0),
                        django.core.validators.MaxValueValidator(25),
                    ],
                )),
                ('last_calculated_at', models.DateTimeField(auto_now=True)),
                ('calculation_version', models.IntegerField(default=1)),
            ],
            options={'db_table': 'nikoscores'},
        ),
        migrations.CreateModel(
            name='NikoScoreEvent',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('student', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,  # Audit log survives student soft-delete
                    related_name='nikoscore_events',
                    to='students.studentprofile',
                )),
                ('event_type', models.CharField(
                    choices=[
                        ('profile_completed', 'Profile Completed'),
                        ('dit_verified', 'DIT Verified'),
                        ('task_submitted', 'Task Submitted'),
                        ('task_reviewed', 'Task Reviewed'),
                        ('submission_abandoned', 'Submission Abandoned'),
                        ('invitation_responded', 'Invitation Responded'),
                        ('activity_decay', 'Activity Decay'),
                        ('profile_updated', 'Profile Updated'),
                    ],
                    max_length=30,
                )),
                ('component', models.CharField(
                    choices=[
                        ('profile', 'Profile'),
                        ('activity', 'Activity'),
                        ('quality', 'Quality'),
                        ('reliability', 'Reliability'),
                    ],
                    max_length=15,
                )),
                ('delta', models.IntegerField()),
                ('score_before', models.IntegerField()),
                ('score_after', models.IntegerField()),
                ('reason', models.TextField()),
                ('source_id', models.UUIDField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={'db_table': 'nikoscore_events'},
        ),
        migrations.AddIndex(
            model_name='nikoscoreevent',
            index=models.Index(fields=['student', 'created_at'], name='nikoscore_events_student_date_idx'),
        ),
    ]
