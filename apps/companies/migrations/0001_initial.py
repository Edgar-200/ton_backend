"""
TON — Companies Initial Migration
Creates companies and watchlist tables.
"""

import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('authentication', '0001_initial'),
        ('students', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Company',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_deleted', models.BooleanField(db_index=True, default=False)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='company_profile',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('company_name', models.CharField(max_length=200)),
                ('brela_number', models.CharField(max_length=100, unique=True)),
                ('brela_document_url', models.URLField(blank=True, max_length=500)),
                ('sector', models.CharField(max_length=100)),
                ('contact_person', models.CharField(max_length=200)),
                ('logo_url', models.URLField(blank=True, max_length=500)),
                ('website', models.URLField(blank=True)),
                ('verification_status', models.CharField(
                    choices=[
                        ('pending', 'Pending'),
                        ('verified', 'Verified'),
                        ('rejected', 'Rejected'),
                    ],
                    db_index=True,
                    default='pending',
                    max_length=10,
                )),
                ('verification_note', models.TextField(blank=True)),
                ('onboarding_stage', models.IntegerField(default=1)),
            ],
            options={
                'db_table': 'companies',
                'verbose_name': 'Company',
                'verbose_name_plural': 'Companies',
            },
        ),
        migrations.CreateModel(
            name='Watchlist',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='watchlist_entries',
                    to='companies.company',
                )),
                ('student', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='watchlisted_by',
                    to='students.studentprofile',
                )),
                ('saved_at', models.DateTimeField(auto_now_add=True)),
                ('note', models.TextField(blank=True, max_length=500)),
            ],
            options={'db_table': 'watchlist'},
        ),
        migrations.AlterUniqueTogether(
            name='watchlist',
            unique_together={('company', 'student')},
        ),
    ]
