# Generated by Django 5.1.4 on 2024-12-26 20:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pyjams', '0003_remove_user_spotify_access_token_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='spotify_username',
            field=models.CharField(blank=True, db_index=True, max_length=64, null=True),
        ),
    ]