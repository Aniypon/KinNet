from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from .models import Family, FamilyMembership, Task, UserProfile


class BasicFlowsTests(TestCase):
	def setUp(self):
		self.user_model = get_user_model()
		self.password = "TestPass12345"
		self.user = self.user_model.objects.create_user(
			username="tester",
			password=self.password,
			first_name="Тест",
			last_name="Пользователь",
		)

	def test_signup_requires_birth_date(self):
		response = self.client.post(
			"/signup/",
			{
				"username": "newuser",
				"full_name": "Иван Иванов",
				"password1": "StrongPass12345",
				"password2": "StrongPass12345",
			},
		)
		self.assertEqual(response.status_code, 200)
		self.assertIn("birth_date", response.context["form"].errors)

	def test_profile_created_on_first_visit(self):
		self.client.login(username=self.user.username, password=self.password)
		response = self.client.get("/profile/")
		self.assertEqual(response.status_code, 200)
		profile = UserProfile.objects.filter(user=self.user).first()
		self.assertIsNotNone(profile)
		self.assertIsNotNone(profile.birth_date)

	def test_task_status_quick_action(self):
		family = Family.objects.create(name="Тестовая семья", created_by=self.user)
		FamilyMembership.objects.create(family=family, user=self.user, role="owner")
		task = Task.objects.create(
			family=family,
			title="Задача",
			created_by=self.user,
			status="todo",
		)

		self.client.login(username=self.user.username, password=self.password)
		response = self.client.post(
			f"/tasks/?family={family.id}",
			{
				"action": "status",
				"task_id": task.id,
				"status": "done",
			},
			follow=True,
		)
		self.assertEqual(response.status_code, 200)
		task.refresh_from_db()
		self.assertEqual(task.status, "done")
