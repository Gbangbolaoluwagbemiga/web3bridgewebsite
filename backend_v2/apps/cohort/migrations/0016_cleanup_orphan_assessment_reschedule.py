# Remove legacy AssessmentReschedule rows with no participant (pre-fix creates never set FK).

from django.db import migrations


def delete_orphan_reschedules(apps, schema_editor):
    AssessmentReschedule = apps.get_model("cohort", "AssessmentReschedule")
    AssessmentReschedule.objects.filter(participant_id__isnull=True).delete()


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("cohort", "0015_assessmentreschedule_participant_and_more"),
    ]

    operations = [
        migrations.RunPython(delete_orphan_reschedules, noop_reverse),
    ]
