from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from core.models import Event, Family, FamilyMember, FamilyMembership, Message, Task


class Command(BaseCommand):
    help = "Create demo family, users, and sample data."

    def handle(self, *args, **options):
        user_model = get_user_model()

        demo_users = [
            {"username": "anna", "password": "demo1234", "full_name": "Анна Иванова"},
            {"username": "ivan", "password": "demo1234", "full_name": "Иван Петров"},
            {"username": "maria", "password": "demo1234", "full_name": "Мария Смирнова"},
            {"username": "sergey", "password": "demo1234", "full_name": "Сергей Иванов"},
            {"username": "olga", "password": "demo1234", "full_name": "Ольга Иванова"},
            {"username": "pavel", "password": "demo1234", "full_name": "Павел Иванов"},
            {"username": "irina", "password": "demo1234", "full_name": "Ирина Иванова"},
        ]

        created_users = []
        for data in demo_users:
            user, created = user_model.objects.get_or_create(username=data["username"])
            if created:
                user.set_password(data["password"])
                parts = data["full_name"].split()
                if parts:
                    user.last_name = parts[0]
                    user.first_name = " ".join(parts[1:])
                user.save()
            created_users.append(user)

        family, _ = Family.objects.get_or_create(name="Семья Ивановых")
        if not family.created_by:
            family.created_by = created_users[0]
            family.save()

        for index, user in enumerate(created_users):
            FamilyMembership.objects.get_or_create(
                family=family,
                user=user,
                defaults={
                    "role": "owner" if index == 0 else "member",
                    "display_order": index,
                },
            )

        FamilyMember.objects.get_or_create(
            family=family,
            first_name="Николай",
            last_name="Иванов",
            relation="Дедушка",
        )
        FamilyMember.objects.get_or_create(
            family=family,
            first_name="Елена",
            last_name="Иванова",
            relation="Бабушка",
        )
        FamilyMember.objects.get_or_create(
            family=family,
            first_name="Артём",
            last_name="Иванов",
            relation="Дядя",
        )
        FamilyMember.objects.get_or_create(
            family=family,
            first_name="София",
            last_name="Иванова",
            relation="Тётя",
        )
        FamilyMember.objects.get_or_create(
            family=family,
            first_name="Кирилл",
            last_name="Иванов",
            relation="Двоюродный брат",
        )
        FamilyMember.objects.get_or_create(
            family=family,
            first_name="Екатерина",
            last_name="Иванова",
            relation="Двоюродная сестра",
        )

        Event.objects.get_or_create(
            family=family,
            title="День рождения Анны",
            date="2026-02-10",
            kind="birthday",
        )

        Task.objects.get_or_create(
            family=family,
            title="Семейный ужин",
            description="Подготовить ужин для всей семьи",
            status="todo",
        )

        Message.objects.get_or_create(
            family=family,
            sender=created_users[0],
            text="Привет! Давайте соберемся на выходных.",
        )

        self.stdout.write(self.style.SUCCESS("Demo data created."))
