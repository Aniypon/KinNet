import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


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
	RECURRENCE_CHOICES = [
		("none", "Не повторять"),
		("daily", "Каждый день"),
		("weekly", "Каждую неделю"),
		("monthly", "Каждый месяц"),
		("yearly", "Каждый год"),
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
	recurrence = models.CharField(max_length=20, choices=RECURRENCE_CHOICES, default="none")
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
	event = models.ForeignKey(
		Event,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="photos",
	)
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

	@property
	def expires_at(self):
		return self.created_at + timedelta(days=7)

	@property
	def days_until_delete(self):
		delta = self.expires_at - timezone.now()
		return max(delta.days, 0)


class Message(models.Model):
	THREAD_CHOICES = [
		("general", "Общий чат"),
		("event", "Событие"),
		("task", "Задача"),
	]

	family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name="messages")
	sender = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="messages_sent",
	)
	reply_to = models.ForeignKey(
		"self",
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="replies",
	)
	thread_type = models.CharField(max_length=20, choices=THREAD_CHOICES, default="general")
	event = models.ForeignKey(Event, on_delete=models.SET_NULL, null=True, blank=True, related_name="chat_messages")
	task = models.ForeignKey(Task, on_delete=models.SET_NULL, null=True, blank=True, related_name="chat_messages")
	attachment = models.FileField(upload_to="chat_attachments/", blank=True)
	attachment_name = models.CharField(max_length=255, blank=True)
	is_pinned = models.BooleanField(default=False)
	text = models.TextField()
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-created_at"]

	def __str__(self) -> str:
		return f"{self.sender}: {self.text[:30]}"


class MessageReaction(models.Model):
	message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="reactions")
	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="message_reactions",
	)
	emoji = models.CharField(max_length=12)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		unique_together = ("message", "user", "emoji")
		ordering = ["emoji", "created_at"]

	def __str__(self) -> str:
		return f"{self.user} {self.emoji} {self.message_id}"


class MessageReadState(models.Model):
	family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name="message_read_states")
	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.CASCADE,
		related_name="message_read_states",
	)
	last_read_message = models.ForeignKey(
		Message,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="+",
	)
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		unique_together = ("family", "user")

	def __str__(self) -> str:
		return f"{self.user} прочитал {self.family}"


class AuditLog(models.Model):
	ACTION_CHOICES = [
		("create", "Создание"),
		("update", "Изменение"),
		("delete", "Удаление"),
		("tree", "Древо"),
		("chat", "Чат"),
	]

	family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name="audit_logs")
	actor = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="audit_logs",
	)
	action = models.CharField(max_length=20, choices=ACTION_CHOICES)
	entity_type = models.CharField(max_length=80)
	entity_id = models.CharField(max_length=80, blank=True)
	summary = models.CharField(max_length=255)
	payload = models.JSONField(default=dict, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ["-created_at"]

	def __str__(self) -> str:
		return self.summary


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
