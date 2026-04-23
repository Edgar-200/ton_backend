"""
TON — Invitations Initial Migration
Creates invitations table with:
  - UniqueConstraint on (company, student) where status in ('sent','viewed')
    → Only one active invitation per company-student pair
  - PROTECT on both FKs → invitation history survives soft-deletes
  - Indexes on (student, status) and (company, status) for inbox queries
"""

import uuid
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
            name='Invitation',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='invitations_sent',
                    to='companies.company',
                )),
                ('student', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='invitations_received',
                    to='students.studentprofile',
                )),
                ('invitation_type', models.CharField(
                    choices=[
                        ('internship', 'Internship'),
                        ('part_time', 'Part-Time'),
                        ('full_time', 'Full-Time'),
                    ],
                    max_length=12,
                )),
                ('message', models.TextField(max_length=1000)),
                ('status', models.CharField(
                    choices=[
                        ('sent', 'Sent'),
                        ('viewed', 'Viewed'),
                        ('accepted', 'Accepted'),
                        ('declined', 'Declined'),
                        ('expired', 'Expired'),
                    ],
                    db_index=True,
                    default='sent',
                    max_length=10,
                )),
                ('contact_released', models.BooleanField(default=False)),
                ('sent_at', models.DateTimeField(auto_now_add=True)),
                ('viewed_at', models.DateTimeField(blank=True, null=True)),
                ('responded_at', models.DateTimeField(blank=True, null=True)),
                ('expires_at', models.DateTimeField()),
            ],
            options={'db_table': 'invitations'},
        ),
        migrations.AddIndex(
            model_name='invitation',
            index=models.Index(fields=['student', 'status'], name='invitations_student_status_idx'),
        ),
        migrations.AddIndex(
            model_name='invitation',
            index=models.Index(fields=['company', 'status'], name='invitations_company_status_idx'),
        ),
        migrations.AddConstraint(
            model_name='invitation',
            constraint=models.UniqueConstraint(
                condition=models.Q(status__in=['sent', 'viewed']),
                fields=['company', 'student'],
                name='unique_active_invitation',
            ),
        ),
    ]
