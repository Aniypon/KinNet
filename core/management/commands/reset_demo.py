from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from core.models import (
    Event,
    Family,
    FamilyInvitation,
    FamilyMember,
    FamilyMembership,
    Message,
    Task,
    TaskChecklistItem,
    TaskContribution,
)


class Command(BaseCommand):
    help = "Delete all data and load demo dataset."

    def handle(self, *args, **options):
        TaskChecklistItem.objects.all().delete()
        TaskContribution.objects.all().delete()
        Message.objects.all().delete()
        Event.objects.all().delete()
        FamilyInvitation.objects.all().delete()
        FamilyMembership.objects.all().delete()
        FamilyMember.objects.all().delete()
        Task.objects.all().delete()
        Family.objects.all().delete()

        user_model = get_user_model()
        user_model.objects.exclude(is_superuser=True).delete()

        self.stdout.write(self.style.SUCCESS("All data removed. Now run seed_demo."))
