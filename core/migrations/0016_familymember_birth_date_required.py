"""Make ``FamilyMember.birth_date`` non-nullable.

The field has been declared as a required ``DateField`` in the model since
its inception, but the original ``0001_initial`` migration accidentally
recorded it as ``null=True, blank=True``. This migration aligns DB state
with the model, defaulting any pre-existing NULL rows to today's date.
"""

from __future__ import annotations

from django.db import migrations, models
from django.utils import timezone


def _backfill(apps, schema_editor):
    FamilyMember = apps.get_model("core", "FamilyMember")
    today = timezone.localdate()
    FamilyMember.objects.filter(birth_date__isnull=True).update(birth_date=today)


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0015_goals_tags_comments_album"),
    ]

    operations = [
        migrations.RunPython(_backfill, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="familymember",
            name="birth_date",
            field=models.DateField(),
        ),
    ]
