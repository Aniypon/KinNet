import uuid

from django.conf import settings
from django.db import models


class Family(models.Model):
	name = models.CharField(max_length=120)
	description = models.TextField(blank=True)
	created_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		related_name="families_created",
	)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		verbose_name_plural = "Families"

	def __str__(self) -> str:
		return self.name


class FamilyMembership(models.Model):
	ROLE_CHOICES = [
		("owner", "Владелец"),
		("admin", "Администратор"),
		("member", "Участник"),
	]

	family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name="memberships")
	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="family_memberships",
	)
	role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="member")
	display_order = models.PositiveIntegerField(default=0)
	joined_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		unique_together = ("family", "user")
		ordering = ["display_order", "joined_at"]

	def __str__(self) -> str:
		return f"{self.user} → {self.family}"


class FamilyMember(models.Model):
	family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name="family_members")
	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="family_profiles",
	)
	first_name = models.CharField(max_length=80)
	last_name = models.CharField(max_length=80, blank=True)
	middle_name = models.CharField(max_length=80, blank=True)
	relation = models.CharField(max_length=80, blank=True)
	birth_date = models.DateField(null=True, blank=True)
	phone = models.CharField(max_length=40, blank=True)
	email = models.EmailField(blank=True)
	address_home = models.CharField(max_length=255, blank=True)
	address_country_house = models.CharField(max_length=255, blank=True)
	socials = models.TextField(blank=True, help_text="Ссылки на соцсети")
	workplace = models.CharField(max_length=255, blank=True)
	notes = models.TextField(blank=True)
	parent1 = models.ForeignKey(
		"self",
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="children_from_parent1",
	)
	parent2 = models.ForeignKey(
		"self",
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="children_from_parent2",
	)
	spouse = models.ForeignKey(
		"self",
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="spouse_of",
	)
	in_tree = models.BooleanField(default=False)
	display_order = models.PositiveIntegerField(default=0)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["display_order", "last_name", "first_name"]

	def __str__(self) -> str:
		full_name = " ".join(part for part in [self.last_name, self.first_name, self.middle_name] if part)
		return full_name or self.first_name


class Event(models.Model):
	EVENT_KIND_CHOICES = [
		("birthday", "День рождения"),
		("holiday", "Праздник"),
		("family", "Семейное событие"),
		("other", "Другое"),
	]

	family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name="events")
	member = models.ForeignKey(
		FamilyMember,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="events",
	)
	title = models.CharField(max_length=160)
	date = models.DateField()
	kind = models.CharField(max_length=20, choices=EVENT_KIND_CHOICES, default="other")
	description = models.TextField(blank=True)
	remind_days_before = models.PositiveIntegerField(default=0)
	created_at = models.DateTimeField(auto_now_add=True)
	tags = models.ManyToManyField("Tag", blank=True, related_name="events")

	def __str__(self) -> str:
		return f"{self.title} ({self.date})"


class Task(models.Model):
	STATUS_CHOICES = [
		("todo", "Нужно сделать"),
		("in_progress", "В процессе"),
		("done", "Готово"),
	]

	family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name="tasks")
	title = models.CharField(max_length=160)
	description = models.TextField(blank=True)
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="todo")
	due_date = models.DateField(null=True, blank=True)
	remind_days_before = models.PositiveIntegerField(default=1)
	assignee = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="assigned_tasks",
	)
	created_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		related_name="tasks_created",
	)
	budget = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
	created_at = models.DateTimeField(auto_now_add=True)
	tags = models.ManyToManyField("Tag", blank=True, related_name="tasks")

	def __str__(self) -> str:
		return self.title


class TaskChecklistItem(models.Model):
	task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="checklist_items")
	title = models.CharField(max_length=200)
	is_done = models.BooleanField(default=False)

	def __str__(self) -> str:
		return self.title


class TaskContribution(models.Model):
	task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="contributions")
	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="task_contributions",
	)
	amount = models.DecimalField(max_digits=12, decimal_places=2)
	comment = models.CharField(max_length=255, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self) -> str:
		return f"{self.user}: {self.amount}"


class Tag(models.Model):
	KIND_CHOICES = [
		("task", "Задачи"),
		("event", "События"),
	]
	name = models.CharField(max_length=60)
	kind = models.CharField(max_length=20, choices=KIND_CHOICES)

	class Meta:
		unique_together = ("name", "kind")
		ordering = ["name"]

	def __str__(self) -> str:
		return self.name


class TaskComment(models.Model):
	task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="comments")
	author = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="task_comments",
	)
	text = models.TextField()
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-created_at"]

	def __str__(self) -> str:
		return f"{self.author}: {self.text[:30]}"


class EventComment(models.Model):
	event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="comments")
	author = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="event_comments",
	)
	text = models.TextField()
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-created_at"]

	def __str__(self) -> str:
		return f"{self.author}: {self.text[:30]}"


class Goal(models.Model):
	family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name="goals")
	title = models.CharField(max_length=160)
	description = models.TextField(blank=True)
	target_amount = models.DecimalField(max_digits=12, decimal_places=2)
	due_date = models.DateField(null=True, blank=True)
	created_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		related_name="goals_created",
	)
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self) -> str:
		return self.title


class GoalContribution(models.Model):
	goal = models.ForeignKey(Goal, on_delete=models.CASCADE, related_name="contributions")
	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="goal_contributions",
	)
	amount = models.DecimalField(max_digits=12, decimal_places=2)
	comment = models.CharField(max_length=255, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self) -> str:
		return f"{self.user}: {self.amount}"


class FamilyPhoto(models.Model):
	family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name="photos")
	image = models.ImageField(upload_to="family_album/")
	caption = models.CharField(max_length=255, blank=True)
	uploaded_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		related_name="family_photos",
	)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-created_at"]

	def __str__(self) -> str:
		return self.caption or f"Фото {self.id}"


class Message(models.Model):
	family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name="messages")
	sender = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="messages_sent",
	)
	text = models.TextField()
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-created_at"]

	def __str__(self) -> str:
		return f"{self.sender}: {self.text[:30]}"


class TelegramProfile(models.Model):
	user = models.OneToOneField(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="telegram_profile",
	)
	chat_id = models.BigIntegerField(unique=True)
	username = models.CharField(max_length=150, blank=True)
	confirm_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
	is_confirmed = models.BooleanField(default=False)
	requested_at = models.DateTimeField(auto_now_add=True)
	confirmed_at = models.DateTimeField(null=True, blank=True)
	linked_at = models.DateTimeField(auto_now_add=True)

	def __str__(self) -> str:
		return f"{self.user} ({self.chat_id})"


class FamilyInvitation(models.Model):
	STATUS_CHOICES = [
		("pending", "Ожидает"),
		("accepted", "Принято"),
		("revoked", "Отозвано"),
	]

	family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name="invitations")
	invited_by = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		related_name="family_invitations_sent",
	)
	token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
	email = models.EmailField(blank=True)
	username = models.CharField(max_length=150, blank=True)
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
	created_at = models.DateTimeField(auto_now_add=True)
	accepted_at = models.DateTimeField(null=True, blank=True)

	def __str__(self) -> str:
		target = self.email or self.username or "invitation"
		return f"{self.family}: {target}"


class UserProfile(models.Model):
	user = models.OneToOneField(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="profile",
	)
	avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
	middle_name = models.CharField(max_length=80, blank=True)
	relation = models.CharField(max_length=80, blank=True)
	birth_date = models.DateField(null=True, blank=True)
	phone = models.CharField(max_length=40, blank=True)
	address_home = models.CharField(max_length=255, blank=True)
	address_country_house = models.CharField(max_length=255, blank=True)
	socials = models.TextField(blank=True, help_text="Ссылки на соцсети")
	workplace = models.CharField(max_length=255, blank=True)
	notes = models.TextField(blank=True)
	parent1 = models.ForeignKey(
		"core.FamilyMember",
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="profiles_as_parent1",
	)
	parent2 = models.ForeignKey(
		"core.FamilyMember",
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="profiles_as_parent2",
	)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self) -> str:
		return f"{self.user} profile"
