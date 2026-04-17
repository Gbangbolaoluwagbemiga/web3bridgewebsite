# Ensures cohort_assessment.breakdown exists when the DB predates or drifted from 0014.

from django.db import migrations


def add_breakdown_if_missing(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'cohort_assessment'
              AND column_name = 'breakdown'
            """
        )
        if cursor.fetchone():
            return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            'ALTER TABLE cohort_assessment ADD COLUMN breakdown jsonb NULL;'
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("cohort", "0016_cleanup_orphan_assessment_reschedule"),
    ]

    operations = [
        migrations.RunPython(add_breakdown_if_missing, noop_reverse),
    ]
