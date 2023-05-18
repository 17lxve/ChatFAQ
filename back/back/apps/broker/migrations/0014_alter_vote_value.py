# Generated by Django 4.1.7 on 2023-04-19 13:14

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("broker", "0013_alter_vote_message"),
    ]

    operations = [
        migrations.AlterField(
            model_name="vote",
            name="value",
            field=models.CharField(
                choices=[("positive", "Positive"), ("negative", "Negative")],
                max_length=255,
            ),
        ),
    ]