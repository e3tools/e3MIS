# Generated by Django 4.2.20 on 2025-05-02 10:09

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("administrativelevels", "0001_initial"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="administrativelevel",
            unique_together={("name", "order")},
        ),
    ]
