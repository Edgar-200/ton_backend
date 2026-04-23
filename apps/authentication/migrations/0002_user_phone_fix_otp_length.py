"""
TON — Add phone field to users and fix otp_code max_length.

otp_code is stored as a Django password hash (make_password) which
produces strings like pbkdf2_sha256$... — these are much longer than 6
characters. max_length=6 would silently truncate the hash, breaking
all OTP verification. Corrected to 128.

phone stores E.164 Tanzanian numbers (+255XXXXXXXXX, max 13 chars).
max_length=20 gives headroom for future international support.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
    ]

    operations = [
        # Fix otp_code field — was max_length=6, must be 128 to fit hashed value
        migrations.AlterField(
            model_name='user',
            name='otp_code',
            field=models.CharField(blank=True, max_length=128, null=True),
        ),
        # Add phone number field
        migrations.AddField(
            model_name='user',
            name='phone',
            field=models.CharField(
                blank=True,
                null=True,
                max_length=20,
                help_text='E.164 format: +255XXXXXXXXX. Optional — OTP always goes to email.',
            ),
        ),
    ]
