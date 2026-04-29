from django import forms
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm

from .models import (
    Event,
    Family,
    FamilyInvitation,
    FamilyMember,
    FamilyMembership,
    Message,
    Task,
    TaskChecklistItem,
    TaskContribution,
    TaskComment,
    EventComment,
    Goal,
    GoalContribution,
    FamilyPhoto,
    Tag,
    UserProfile,
)


class FamilyForm(forms.ModelForm):
    class Meta:
        model = Family
        fields = ["name", "description"]
        labels = {
            "name": "Название",
            "description": "Описание",
        }


class FamilyMembershipRoleForm(forms.ModelForm):
    class Meta:
        model = FamilyMembership
        fields = ["role"]


class FamilyInvitationForm(forms.ModelForm):
    class Meta:
        model = FamilyInvitation
        fields = ["username"]

    def clean(self):
        cleaned = super().clean()
        username = cleaned.get("username")
        if not username:
            raise forms.ValidationError("Укажите никнейм.")
        return cleaned


class SignupForm(UserCreationForm):
    full_name = forms.CharField(label="ФИО", max_length=150)
    birth_date = forms.DateField(
        label="Дата рождения",
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "full_name", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Никнейм"

    def save(self, commit=True):
        user = super().save(commit=False)
        full_name = self.cleaned_data.get("full_name", "").strip()
        if full_name:
            parts = full_name.split()
            if len(parts) >= 2:
                user.last_name = parts[0]
                user.first_name = " ".join(parts[1:])
            else:
                user.first_name = full_name
        if commit:
            user.save()
            UserProfile.objects.update_or_create(
                user=user,
                defaults={"birth_date": self.cleaned_data.get("birth_date")},
            )
        return user


class UserProfileForm(forms.ModelForm):
    first_name = forms.CharField(label="Имя", max_length=150)
    last_name = forms.CharField(label="Фамилия", max_length=150, required=False)
    email = forms.EmailField(label="Email", required=False)

    class Meta:
        model = UserProfile
        fields = [
            "avatar",
            "middle_name",
            "relation",
            "birth_date",
            "phone",
            "address_home",
            "address_country_house",
            "socials",
            "workplace",
            "notes",
            "parent1",
            "parent2",
        ]
        widgets = {
            "birth_date": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "avatar": "Аватар",
            "middle_name": "Отчество",
            "relation": "Родство",
            "birth_date": "Дата рождения",
            "phone": "Телефон",
            "address_home": "Адрес (дом)",
            "address_country_house": "Адрес (дача)",
            "socials": "Соцсети",
            "workplace": "Место работы",
            "notes": "Заметки",
            "parent1": "Родитель 1",
            "parent2": "Родитель 2",
        }
        help_texts = {
            "socials": "Ссылки на соцсети",
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_instance = user
        if user is not None:
            self.fields["first_name"].initial = user.first_name
            self.fields["last_name"].initial = user.last_name
            self.fields["email"].initial = user.email
            queryset = FamilyMember.objects.filter(
                family__memberships__user=user
            ).distinct()
            self.fields["parent1"].queryset = queryset
            self.fields["parent2"].queryset = queryset
        if self.instance and self.instance.birth_date:
            self.fields["birth_date"].initial = self.instance.birth_date

        self.order_fields(
            [
                "first_name",
                "last_name",
                "middle_name",
                "relation",
                "birth_date",
                "phone",
                "email",
                "address_home",
                "address_country_house",
                "socials",
                "workplace",
                "notes",
                "parent1",
                "parent2",
            ]
        )

    def save(self, commit=True):
        profile = super().save(commit=False)
        user = self.user_instance or profile.user
        if not self.cleaned_data.get("birth_date"):
            profile.birth_date = profile.birth_date or timezone.localdate()
        if user is not None:
            user.first_name = self.cleaned_data.get("first_name", "").strip()
            user.last_name = self.cleaned_data.get("last_name", "").strip()
            user.email = self.cleaned_data.get("email", "").strip()
            if commit:
                user.save()
        if commit:
            profile.save()
        return profile

    def clean_birth_date(self):
        birth_date = self.cleaned_data.get("birth_date")
        if not birth_date:
            raise forms.ValidationError("Укажите дату рождения.")
        return birth_date


class FamilyMemberForm(forms.ModelForm):
    class Meta:
        model = FamilyMember
        fields = [
            "first_name",
            "last_name",
            "middle_name",
            "relation",
            "birth_date",
            "phone",
            "email",
            "address_home",
            "address_country_house",
            "socials",
            "workplace",
            "notes",
            "parent1",
            "parent2",
        ]
        widgets = {
            "birth_date": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "first_name": "Имя",
            "last_name": "Фамилия",
            "middle_name": "Отчество",
            "relation": "Родство",
            "birth_date": "Дата рождения",
            "phone": "Телефон",
            "email": "Email",
            "address_home": "Адрес (дом)",
            "address_country_house": "Адрес (дача)",
            "socials": "Соцсети",
            "workplace": "Место работы",
            "notes": "Заметки",
            "parent1": "Родитель 1",
            "parent2": "Родитель 2",
        }

    def __init__(self, *args, family=None, **kwargs):
        super().__init__(*args, **kwargs)
        if family is not None:
            queryset = family.family_members.all()
            self.fields["parent1"].queryset = queryset
            self.fields["parent2"].queryset = queryset


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ["title", "date", "kind", "member", "description", "remind_days_before", "tags"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "title": "Название",
            "date": "Дата",
            "kind": "Тип",
            "member": "Участник",
            "description": "Описание",
            "remind_days_before": "Напомнить за (дней)",
            "tags": "Метки",
        }

    def __init__(self, *args, family=None, **kwargs):
        super().__init__(*args, **kwargs)
        if family is not None:
            self.fields["member"].queryset = family.family_members.all()
        self.fields["tags"].queryset = Tag.objects.filter(kind="event")


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = [
            "title",
            "description",
            "status",
            "due_date",
            "remind_days_before",
            "assignee",
            "budget",
            "tags",
        ]
        widgets = {
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "title": "Название",
            "description": "Описание",
            "status": "Статус",
            "due_date": "Срок",
            "remind_days_before": "Напомнить за (дней)",
            "assignee": "Ответственный",
            "budget": "Бюджет",
            "tags": "Метки",
        }

    def __init__(self, *args, family=None, **kwargs):
        super().__init__(*args, **kwargs)
        if family is not None:
            user_model = get_user_model()
            self.fields["assignee"].queryset = user_model.objects.filter(
                family_memberships__family=family
            ).distinct()
        self.fields["tags"].queryset = Tag.objects.filter(kind="task")


class TaskChecklistItemForm(forms.ModelForm):
    class Meta:
        model = TaskChecklistItem
        fields = ["title", "is_done"]
        labels = {
            "title": "Пункт",
            "is_done": "Выполнено",
        }


class TaskContributionForm(forms.ModelForm):
    class Meta:
        model = TaskContribution
        fields = ["user", "amount", "comment"]
        labels = {
            "user": "Участник",
            "amount": "Сумма",
            "comment": "Комментарий",
        }

    def __init__(self, *args, family=None, **kwargs):
        super().__init__(*args, **kwargs)
        if family is not None:
            user_model = get_user_model()
            self.fields["user"].queryset = user_model.objects.filter(
                family_memberships__family=family
            ).distinct()


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ["text"]
        widgets = {
            "text": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "text": "Сообщение",
        }


class TaskCommentForm(forms.ModelForm):
    class Meta:
        model = TaskComment
        fields = ["text"]
        widgets = {
            "text": forms.Textarea(attrs={"rows": 3, "placeholder": "Комментарий"}),
        }
        labels = {
            "text": "Комментарий",
        }


class EventCommentForm(forms.ModelForm):
    class Meta:
        model = EventComment
        fields = ["text"]
        widgets = {
            "text": forms.Textarea(attrs={"rows": 3, "placeholder": "Комментарий"}),
        }
        labels = {
            "text": "Комментарий",
        }


class GoalForm(forms.ModelForm):
    class Meta:
        model = Goal
        fields = ["title", "description", "target_amount", "due_date"]
        widgets = {
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {
            "title": "Название",
            "description": "Описание",
            "target_amount": "Цель (сумма)",
            "due_date": "Срок",
        }


class GoalContributionForm(forms.ModelForm):
    class Meta:
        model = GoalContribution
        fields = ["user", "amount", "comment"]
        labels = {
            "user": "Участник",
            "amount": "Сумма",
            "comment": "Комментарий",
        }

    def __init__(self, *args, family=None, **kwargs):
        super().__init__(*args, **kwargs)
        if family is not None:
            user_model = get_user_model()
            self.fields["user"].queryset = user_model.objects.filter(
                family_memberships__family=family
            ).distinct()


class FamilyPhotoForm(forms.ModelForm):
    class Meta:
        model = FamilyPhoto
        fields = ["image", "caption"]
        labels = {
            "image": "Фотография",
            "caption": "Подпись",
        }
