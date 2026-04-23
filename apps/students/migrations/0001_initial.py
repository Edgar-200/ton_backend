"""
TON — Students Initial Migration
Creates student_profiles table with soft delete, verification states, and JSONField sectors.
"""

import uuid
import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('authentication', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='StudentProfile',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_deleted', models.BooleanField(db_index=True, default=False)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='student_profile',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('full_name', models.CharField(max_length=200)),
                ('dit_student_id', models.CharField(max_length=50, unique=True)),
                ('course', models.CharField(
                    choices=[
                        ('civil_engineering', 'Civil Engineering'),
                        ('ict', 'Information & Communication Technology'),
                        ('electrical', 'Electrical Engineering'),
                        ('architecture', 'Architecture'),
                        ('business', 'Business Administration'),
                        ('mechanical', 'Mechanical Engineering'),
                        ('water', 'Water Resources Engineering'),
                        ('other', 'Other'),
                    ],
                    max_length=100,
                )),
                ('year_of_study', models.IntegerField(
                    validators=[
                        django.core.validators.MinValueValidator(1),
                        django.core.validators.MaxValueValidator(5),
                    ],
                )),
                ('bio', models.TextField(blank=True, max_length=1000)),
                ('profile_photo_url', models.URLField(blank=True, max_length=500)),
                ('dit_id_document_url', models.URLField(blank=True, max_length=500)),
                ('verification_status', models.CharField(
                    choices=[
                        ('unsubmitted', 'Unsubmitted'),
                        ('pending', 'Pending'),
                        ('verified', 'Verified'),
                        ('rejected', 'Rejected'),
                    ],
                    db_index=True,
                    default='unsubmitted',
                    max_length=15,
                )),
                ('verification_note', models.TextField(blank=True)),
                ('sectors', models.JSONField(default=list)),
                ('profile_completion_pct', models.IntegerField(default=0)),
            ],
            options={
                'db_table': 'student_profiles',
                'verbose_name': 'Student Profile',
                'verbose_name_plural': 'Student Profiles',
            },
        ),
    ]
