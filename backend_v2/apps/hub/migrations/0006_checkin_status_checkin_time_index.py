# Generated manually for query performance (status + check_in_time filters)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("hub", "0005_blockeddaterange"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="checkin",
            index=models.Index(
                fields=["status", "check_in_time"],
                name="checkin_status_checkin_time_idx",
            ),
        ),
    ]
