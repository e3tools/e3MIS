from django.db import migrations, models
import django.db.models.deletion


def copy_m2m_data(apps, schema_editor):
    """Copy data from auto-generated M2M table to new through model table."""
    FollowUpEventTrackableObject = apps.get_model('trackableobjects', 'FollowUpEventTrackableObject')
    db_alias = schema_editor.connection.alias

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT followupevent_id, trackableobject_id "
            "FROM trackableobjects_followupevent_trackable_objects"
        )
        rows = cursor.fetchall()

    for follow_up_event_id, trackable_object_id in rows:
        FollowUpEventTrackableObject.objects.using(db_alias).create(
            follow_up_event_id=follow_up_event_id,
            trackable_object_id=trackable_object_id,
            order=0,
        )


def reverse_copy(apps, schema_editor):
    """Reverse is not supported — data stays in through table."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('trackableobjects', '0016_add_restrict_by_administrative_units_to_instance'),
    ]

    operations = [
        # 1. Create the through model table
        migrations.CreateModel(
            name='FollowUpEventTrackableObject',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order', models.PositiveIntegerField(default=0)),
                ('follow_up_event', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='trackableobjects.followupevent',
                )),
                ('trackable_object', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='trackableobjects.trackableobject',
                )),
            ],
            options={
                'ordering': ['order'],
                'unique_together': {('follow_up_event', 'trackable_object')},
            },
        ),
        # 2. Copy existing M2M rows into through table
        migrations.RunPython(copy_m2m_data, reverse_copy),
        # 3. Remove old auto-managed M2M field (drops auto table)
        migrations.RemoveField(
            model_name='followupevent',
            name='trackable_objects',
        ),
        # 4. Re-add M2M field pointing to through model
        migrations.AddField(
            model_name='followupevent',
            name='trackable_objects',
            field=models.ManyToManyField(
                blank=True,
                related_name='follow_up_events',
                through='trackableobjects.FollowUpEventTrackableObject',
                to='trackableobjects.trackableobject',
            ),
        ),
    ]
