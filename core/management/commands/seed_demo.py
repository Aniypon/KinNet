from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.budget.models import Expense, Wishlist, WishlistItem
from apps.cookbook.models import Ingredient, Recipe, ShoppingItem, ShoppingList
from apps.gamification.services import award, ensure_default_badges
from apps.health.models import HealthRecord, Medication
from apps.polls.models import Poll, PollChoice, PollVote
from apps.timecapsule.models import Capsule
from core.models import (
    Event,
    Family,
    FamilyMember,
    FamilyMembership,
    Goal,
    GoalContribution,
    Message,
    MessageReaction,
    Task,
    TaskChecklistItem,
    TaskComment,
)


class Command(BaseCommand):
    help = "Create demo family, users, and sample data."

    def handle(self, *args, **options):
        user_model = get_user_model()
        today = timezone.localdate()

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

        ensure_default_badges()
        target_families = [family]
        for existing_family in Family.objects.filter(name__icontains="QA"):
            if existing_family.id != family.id:
                target_families.append(existing_family)
        for target_family in target_families:
            family_users = list(
                user_model.objects.filter(family_memberships__family=target_family).distinct()
            ) or created_users
            self._seed_family(target_family, family_users, today)

        self.stdout.write(self.style.SUCCESS("Demo data created."))

    def _member(self, family, first_name, last_name, **defaults):
        member, _ = FamilyMember.objects.update_or_create(
            family=family,
            first_name=first_name,
            last_name=last_name,
            defaults=defaults,
        )
        return member

    def _pair(self, first, second):
        first.spouse = second
        first.in_tree = True
        second.spouse = first
        second.in_tree = True
        first.save(update_fields=["spouse", "in_tree"])
        second.save(update_fields=["spouse", "in_tree"])

    def _seed_family(self, family, users, today):
        def user(index):
            return users[index % len(users)]

        members = [
            self._member(family, "Николай", "Иванов", relation="дедушка", birth_date="1949-04-12", phone="+7 900 100-10-10", in_tree=True, display_order=0),
            self._member(family, "Елена", "Иванова", relation="бабушка", birth_date="1952-09-03", phone="+7 900 100-10-11", in_tree=True, display_order=1),
            self._member(family, "Артём", "Иванов", relation="сын", birth_date="1978-06-18", email="artem@example.test", in_tree=True, display_order=2),
            self._member(family, "София", "Иванова", relation="дочь", birth_date="1981-02-24", workplace="Школа N 17", in_tree=True, display_order=3),
            self._member(family, "Екатерина", "Иванова", relation="дочь", birth_date="1985-11-08", in_tree=True, display_order=4),
            self._member(family, "Кирилл", "Иванов", relation="внук", birth_date="2007-07-15", in_tree=True, display_order=5),
            self._member(family, "Мила", "Иванова", relation="внучка", birth_date="2012-05-09", in_tree=True, display_order=6),
            self._member(family, "Глеб", "Иванов", relation="внук", birth_date="2016-12-01", in_tree=True, display_order=7),
            self._member(family, "Ольга", "Орлова", relation="супруга Артёма", birth_date="1980-03-17", in_tree=True, display_order=8),
            self._member(family, "Павел", "Смирнов", relation="супруг Софии", birth_date="1979-10-29", in_tree=True, display_order=9),
            self._member(family, "Анна", "Смирнова", relation="правнучка", birth_date="2020-08-21", in_tree=True, display_order=10),
            self._member(family, "Тимофей", "Иванов", relation="правнук", birth_date="2023-01-14", in_tree=True, display_order=11),
        ]
        nikolay, elena, artem, sofia, ekaterina, kirill, mila, gleb, olga, pavel, anna, timofey = members
        self._pair(nikolay, elena)
        self._pair(artem, olga)
        self._pair(sofia, pavel)
        for child in [artem, sofia, ekaterina]:
            child.parent1 = nikolay
            child.parent2 = elena
            child.in_tree = True
            child.save(update_fields=["parent1", "parent2", "in_tree"])
        for child in [kirill, mila, gleb]:
            child.parent1 = artem
            child.parent2 = olga
            child.in_tree = True
            child.save(update_fields=["parent1", "parent2", "in_tree"])
        anna.parent1 = sofia
        anna.parent2 = pavel
        anna.save(update_fields=["parent1", "parent2"])
        timofey.parent1 = kirill
        timofey.save(update_fields=["parent1"])

        events = [
            ("День рождения Елены", today.replace(month=9, day=3), "birthday", elena),
            ("Семейный пикник в парке", today + timedelta(days=9), "family", None),
            ("Школьный концерт Милы", today + timedelta(days=16), "family", mila),
            ("Годовщина Николая и Елены", today + timedelta(days=31), "holiday", None),
        ]
        for title, date, kind, member in events:
            Event.objects.update_or_create(
                family=family,
                title=title,
                defaults={
                    "date": date,
                    "kind": kind,
                    "recurrence": "yearly" if kind == "birthday" else "none",
                    "member": member,
                    "description": "Добавлено для демонстрации семейного календаря.",
                },
            )

        tasks = [
            ("Купить продукты к пикнику", "Сверить список покупок и распределить, кто что берёт.", "todo", user(0)),
            ("Забронировать стол на годовщину", "Позвонить в семейное кафе и уточнить посадку у окна.", "in_progress", user(1)),
            ("Разобрать старые фотографии", "Отобрать снимки для семейного альбома.", "todo", user(2)),
            ("Подготовить подарок Елене", "Собрать идеи от всех внуков.", "done", user(3)),
        ]
        task_objects = []
        for title, description, status, assignee in tasks:
            task, _ = Task.objects.update_or_create(
                family=family,
                title=title,
                defaults={"description": description, "status": status, "assignee": assignee, "created_by": user(0), "due_date": today + timedelta(days=7)},
            )
            task_objects.append(task)
            for checklist_title in ["Ответственный назначен", "Срок согласован"]:
                TaskChecklistItem.objects.get_or_create(task=task, title=checklist_title)
            TaskComment.objects.get_or_create(task=task, author=user(1), text="Берусь помочь, если что-то останется без ответственного.")

        messages = [
            (user(0), "Кто сможет забрать продукты для пикника в пятницу?", "general", None),
            (user(1), "Я возьму овощи и воду. Список уже обновила в покупках.", "general", None),
            (user(2), "Добавил старые фото с дачи в подборку для альбома.", "general", None),
            (user(3), "По годовщине: ресторан подтвердил свободный зал.", "event", None),
            (user(0), "Не забудьте проголосовать за место встречи на июнь.", "task", task_objects[0]),
        ]
        previous = None
        for sender, text, thread_type, task in messages:
            message, _ = Message.objects.get_or_create(
                family=family,
                sender=sender,
                text=text,
                defaults={"thread_type": thread_type, "task": task, "reply_to": previous, "is_pinned": text.startswith("Не забудьте")},
            )
            previous = message
            MessageReaction.objects.get_or_create(message=message, user=user(1), emoji="👍")
            MessageReaction.objects.get_or_create(message=message, user=user(2), emoji="❤️")

        recipes = [
            ("Сырники Елены", "Нежные сырники на семейный завтрак.", "творог|500|г\nяйцо|1|шт\nмука|4|ст. л.\nсахар|2|ст. л.", 30, 4, "завтрак, дети"),
            ("Пирог с яблоками", "Тот самый пирог к воскресному чаю.", "яблоки|5|шт\nмука|220|г\nкорица|1|ч. л.\nсливочное масло|120|г", 55, 8, "выпечка"),
            ("Салат для пикника", "Быстрый салат, который удобно брать с собой.", "огурцы|4|шт\nпомидоры|5|шт\nсыр|200|г\nзелень|1|пучок", 15, 6, "пикник"),
        ]
        for title, description, ingredients, minutes, servings, tags in recipes:
            recipe, _ = Recipe.objects.update_or_create(
                family=family,
                title=title,
                defaults={"author": user(0), "description": description, "instructions": "Смешать ингредиенты, готовить спокойно и пробовать по вкусу.", "cook_time_minutes": minutes, "servings": servings, "tags": tags},
            )
            for line in ingredients.splitlines():
                name, quantity, unit = line.split("|")
                Ingredient.objects.get_or_create(recipe=recipe, name=name, defaults={"quantity": quantity, "unit": unit})

        shopping_list, _ = ShoppingList.objects.update_or_create(
            family=family,
            name="Пикник на выходных",
            defaults={"created_by": user(1), "linked_task": task_objects[0]},
        )
        for name, quantity, done in [
            ("Минеральная вода", "6 бутылок", False),
            ("Фрукты", "2 кг", False),
            ("Салфетки", "1 упаковка", True),
            ("Сыр", "400 г", False),
        ]:
            ShoppingItem.objects.update_or_create(shopping_list=shopping_list, name=name, defaults={"quantity": quantity, "is_done": done})

        for title, amount, category in [
            ("Продукты для ужина", "4280.00", "Еда"),
            ("Подарок Елене", "6500.00", "Подарки"),
            ("Билеты на концерт", "3600.00", "Досуг"),
        ]:
            Expense.objects.update_or_create(
                family=family,
                title=title,
                defaults={"payer": user(0), "amount": amount, "category": category, "spent_on": today, "notes": "Демо-расход"},
            )

        wishlist, _ = Wishlist.objects.update_or_create(family=family, owner_member=mila, defaults={"title": "Идеи подарков для Милы"})
        for title, price in [("Набор акварели", "1800.00"), ("Книга про космос", "950.00"), ("Билеты в планетарий", "2400.00")]:
            WishlistItem.objects.update_or_create(wishlist=wishlist, title=title, defaults={"price_estimate": price, "description": "Идея для ближайшего праздника."})

        goal, _ = Goal.objects.update_or_create(
            family=family,
            title="Семейная поездка к морю",
            defaults={"description": "Копим на общую летнюю поездку.", "target_amount": "180000.00", "due_date": today + timedelta(days=120), "created_by": user(0)},
        )
        GoalContribution.objects.get_or_create(goal=goal, user=user(0), amount="25000.00", defaults={"comment": "Первый взнос"})
        GoalContribution.objects.get_or_create(goal=goal, user=user(1), amount="18000.00", defaults={"comment": "На билеты"})

        poll, _ = Poll.objects.update_or_create(
            family=family,
            question="Где провести июньскую встречу?",
            defaults={"author": user(2), "description": "Выбираем место заранее.", "allow_multiple": False},
        )
        for choice_text in ["Парк у реки", "Дача", "Кафе рядом с домом"]:
            choice, _ = PollChoice.objects.get_or_create(poll=poll, text=choice_text)
            PollVote.objects.get_or_create(choice=choice, user=user(0))

        for member, blood_type, allergies in [(elena, "A+", "Пыльца"), (kirill, "O+", "Нет"), (mila, "B+", "Клубника")]:
            HealthRecord.objects.update_or_create(member=member, defaults={"blood_type": blood_type, "allergies": allergies, "emergency_contact": str(artem), "notes": "Демо-карточка здоровья"})
        Medication.objects.update_or_create(member=elena, name="Витамин D", defaults={"dosage": "1000 МЕ", "frequency": "daily", "times": "09:00", "starts_on": today, "is_active": True})

        capsule, _ = Capsule.objects.update_or_create(
            family=family,
            title="Письмо Анне на 18-летие",
            defaults={"author": user(0), "message": "Анна, это семейное письмо из прошлого.", "reveal_at": timezone.now() + timedelta(days=365 * 10), "recipient_member": anna},
        )
        capsule.recipients_users.set(users[:2])

        for code in ["hearth_keeper", "family_chef", "planner", "voter"]:
            award(user(0), code)
