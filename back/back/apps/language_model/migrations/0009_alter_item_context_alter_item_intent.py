# Generated by Django 4.1.10 on 2023-08-09 19:00

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("language_model", "0008_alter_dataset_original_file"),
    ]

    operations = [
        migrations.AlterField(
            model_name="item",
            name="context",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="item",
            name="intent",
            field=models.TextField(blank=True, null=True),
        ),
    ]
