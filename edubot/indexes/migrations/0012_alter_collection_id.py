# Generated by Django 4.1.8 on 2024-04-01 11:45

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("indexes", "0011_collection_id_alter_collection_uuid"),
    ]

    operations = [
        migrations.AlterField(
            model_name="collection",
            name="id",
            field=models.BigAutoField(
                auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
            ),
        ),
    ]
