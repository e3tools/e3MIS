# Written by hand: makemigrations asks interactively for a default for existing rows.
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('subprojects', '0022_rename_trackable_object_response_attachment_trackable_object_instance'),
    ]

    operations = [
        migrations.AddField(
            model_name='attachment',
            name='client_uuid',
            field=models.UUIDField(blank=True, editable=False, null=True, unique=True),
        ),
        # Existing attachments get the migration time; their real upload time was never recorded.
        migrations.AddField(
            model_name='attachment',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='attachment',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
