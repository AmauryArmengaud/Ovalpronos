from django.core.management import call_command
from django.db import migrations


def create_cache_table(apps, schema_editor):
    # createcachetable is idempotent; running it here means deploy.sh's `migrate`
    # creates the rate-limit cache table without a manual step on the VPS
    call_command('createcachetable', database=schema_editor.connection.alias, verbosity=0)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_add_last_reminder_sent'),
    ]

    operations = [
        migrations.RunPython(create_cache_table, migrations.RunPython.noop),
    ]
