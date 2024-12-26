# Generated by Django 5.1.4 on 2024-12-26 19:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pyjams', '0002_user_spotify_email'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='spotify_access_token',
        ),
        migrations.RemoveField(
            model_name='user',
            name='spotify_refresh_token',
        ),
        migrations.RemoveField(
            model_name='user',
            name='spotify_token_expires_at',
        ),
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(choices=[('guest', 'GUEST'), ('user', 'USER'), ('manager', 'MANAGER'), ('moderator', 'MODERATOR'), ('admin', 'ADMIN')], default='user', max_length=20),
        ),
    ]
