# Generated by Django 4.1.4 on 2023-01-24 14:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("broker", "0008_customwsplatformconfig_telegramplatformconfig_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="platformconfig",
            name="platform_meta",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]