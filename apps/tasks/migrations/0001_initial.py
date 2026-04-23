"""
TON — Tasks Initial Migration
Creates tasks and submissions tables with all required indexes.

Critical indexes per system design document:
  tasks: (sector, status) composite, deadline
  submissions: (task, student) unique, (task, status), (student, submitted_at)
"""

import uuid
import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('companies', '0001_initial'),
        ('students', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Task',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_deleted', models.BooleanField(db_index=True, default=False)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='tasks',
                    to='companies.company',
                )),
                ('title', models.CharField(max_length=300)),
                ('description', models.TextField()),
                ('sector', models.CharField(db_index=True, max_length=100)),
                ('skill_tags', models.JSONField(default=list)),
                ('deadline', models.DateTimeField(db_index=True)),
                ('status', models.CharField(
                    choices=[
                        ('active', 'Active'),
                        ('closed', 'Closed'),
                        ('archived', 'Archived'),
                    ],
                    db_index=True,
                    default='active',
                    max_length=10,
                )),
                ('max_submissions', models.IntegerField(blank=True, null=True)),
                ('submissions_count', models.IntegerField(default=0)),
            ],
            options={'db_table': 'tasks'},
        ),
        migrations.AddIndex(
            model_name='task',
            index=models.Index(fields=['sector', 'status'], name='tasks_sector_status_idx'),
        ),
        migrations.AddIndex(
            model_name='task',
            index=models.Index(fields=['deadline'], name='tasks_deadline_idx'),
        ),
        migrations.CreateModel(
            name='Submission',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('task', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='submissions',
                    to='tasks.task',
                )),
                ('student', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='submissions',
                    to='students.studentprofile',
                )),
                ('content_text', models.TextField(blank=True)),
                ('file_url', models.URLField(blank=True, max_length=500)),
                ('external_link', models.URLField(blank=True, max_length=500)),
                ('company_score', models.IntegerField(
                    blank=True,
                    null=True,
                    validators=[
                        django.core.validators.MinValueValidator(1),
                        django.core.validators.MaxValueValidator(5),
                    ],
                )),
                ('company_feedback', models.TextField(blank=True)),
                ('status', models.CharField(
                    choices=[
                        ('submitted', 'Submitted'),
                        ('reviewed', 'Reviewed'),
                        ('abandoned', 'Abandoned'),
                    ],
                    default='submitted',
                    max_length=10,
                )),
                ('submitted_at', models.DateTimeField(auto_now_add=True)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('nikoscore_processed', models.BooleanField(default=False)),
            ],
            options={'db_table': 'submissions'},
        ),
        migrations.AlterUniqueTogether(
            name='submission',
            unique_together={('task', 'student')},
        ),
        migrations.AddIndex(
            model_name='submission',
            index=models.Index(fields=['task', 'status'], name='submissions_task_status_idx'),
        ),
        migrations.AddIndex(
            model_name='submission',
            index=models.Index(fields=['student', 'submitted_at'], name='submissions_student_date_idx'),
        ),
    ]
