from django.db import migrations


def fix_duplicate_orders(apps, schema_editor):
    FollowUpEvent = apps.get_model('trackableobjects', 'FollowUpEvent')
    for index, event in enumerate(FollowUpEvent.objects.order_by('order', 'name'), start=1):
        if event.order != index:
            FollowUpEvent.objects.filter(pk=event.pk).update(order=index)


class Migration(migrations.Migration):

    dependencies = [
        ('trackableobjects', '0019_global_followupevent_order'),
    ]

    operations = [
        migrations.RunPython(fix_duplicate_orders, migrations.RunPython.noop),
    ]
