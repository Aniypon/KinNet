from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0009_familymember_in_tree"),
    ]

    operations = [
        migrations.AddField(
            model_name="telegramprofile",
            name="confirm_token",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
        migrations.AddField(
            model_name="telegramprofile",
            name="is_confirmed",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="telegramprofile",
            name="requested_at",
            field=models.DateTimeField(auto_now_add=True),
        ),
        migrations.AddField(
            model_name="telegramprofile",
            name="confirmed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
