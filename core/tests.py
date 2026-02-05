import json
import tempfile
import zipfile
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.utils import override_settings
from django.utils import timezone
from PIL import Image

from .forms import EventForm
from .models import Event, Family, FamilyMember, FamilyMembership, FamilyPhoto, Message, MessageReaction, Task, UserProfile
from .utils import get_next_event_date
from .services.family_tree import FamilyTreeValidationError, apply_relation_action, validate_family_tree


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

	def test_album_accepts_multiple_photos_in_one_upload(self):
		family = Family.objects.create(name="Тестовая семья", created_by=self.user)
		FamilyMembership.objects.create(family=family, user=self.user, role="owner")

		def photo_upload(name):
			buffer = BytesIO()
			Image.new("RGB", (2, 2), color="white").save(buffer, format="PNG")
			return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")

		self.client.login(username=self.user.username, password=self.password)
		with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
			response = self.client.post(
				f"/album/?family={family.id}",
				{
					"images": [photo_upload("first.png"), photo_upload("second.png")],
					"caption": "Летние выходные",
				},
				follow=True,
			)

		self.assertEqual(response.status_code, 200)
		photos = FamilyPhoto.objects.filter(family=family, uploaded_by=self.user)
		self.assertEqual(photos.count(), 2)
		self.assertTrue(all(photo.caption == "Летние выходные" for photo in photos))

	def test_album_groups_photos_by_event_and_unlinked_folder(self):
		family = Family.objects.create(name="Тестовая семья", created_by=self.user)
		FamilyMembership.objects.create(family=family, user=self.user, role="owner")
		event = Event.objects.create(family=family, title="День рождения Елены", date=timezone.localdate())

		self.client.login(username=self.user.username, password=self.password)
		with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
			linked_photo = SimpleUploadedFile("event.png", self._image_bytes(), content_type="image/png")
			unlinked_photo = SimpleUploadedFile("free.png", self._image_bytes(), content_type="image/png")
			FamilyPhoto.objects.create(family=family, event=event, image=linked_photo, uploaded_by=self.user)
			FamilyPhoto.objects.create(family=family, image=unlinked_photo, uploaded_by=self.user)

			response = self.client.get(f"/album/?family={family.id}")

		self.assertContains(response, "День рождения Елены")
		self.assertContains(response, "Без привязки к событию")
		self.assertContains(response, "Скачать оригинал", count=2)

	def test_album_preview_is_resized_and_original_download_is_available(self):
		family = Family.objects.create(name="Тестовая семья", created_by=self.user)
		FamilyMembership.objects.create(family=family, user=self.user, role="owner")

		self.client.login(username=self.user.username, password=self.password)
		with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
			upload = SimpleUploadedFile("large.png", self._image_bytes(size=(900, 700)), content_type="image/png")
			photo = FamilyPhoto.objects.create(family=family, image=upload, uploaded_by=self.user)

			preview = self.client.get(f"/album/photos/{photo.id}/preview/")
			download = self.client.get(f"/album/photos/{photo.id}/download/")
			download_body = b"".join(download.streaming_content)

		self.assertEqual(preview.status_code, 200)
		self.assertEqual(preview["Content-Type"], "image/jpeg")
		with Image.open(BytesIO(preview.content)) as preview_image:
			self.assertLessEqual(max(preview_image.size), 560)

		self.assertEqual(download.status_code, 200)
		self.assertIn("attachment", download["Content-Disposition"])
		self.assertGreater(len(download_body), 0)

	def test_album_download_returns_zip_for_selected_folder(self):
		family = Family.objects.create(name="Тестовая семья", created_by=self.user)
		FamilyMembership.objects.create(family=family, user=self.user, role="owner")
		event = Event.objects.create(family=family, title="День рождения Елены", date=timezone.localdate())

		self.client.login(username=self.user.username, password=self.password)
		with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
			linked_photo = SimpleUploadedFile("event.png", self._image_bytes(), content_type="image/png")
			unlinked_photo = SimpleUploadedFile("free.png", self._image_bytes(), content_type="image/png")
			FamilyPhoto.objects.create(family=family, event=event, image=linked_photo, uploaded_by=self.user)
			FamilyPhoto.objects.create(family=family, image=unlinked_photo, uploaded_by=self.user)

			event_response = self.client.get(f"/album/download/?family={family.id}&event={event.id}")
			event_archive_body = b"".join(event_response.streaming_content)
			unlinked_response = self.client.get(f"/album/download/?family={family.id}&unlinked=1")
			unlinked_archive_body = b"".join(unlinked_response.streaming_content)

		self.assertEqual(event_response.status_code, 200)
		self.assertEqual(event_response["Content-Type"], "application/zip")
		self.assertIn("attachment", event_response["Content-Disposition"])
		with zipfile.ZipFile(BytesIO(event_archive_body)) as archive:
			event_names = archive.namelist()
		self.assertEqual(event_names, ["День рождения Елены/event.png"])

		self.assertEqual(unlinked_response.status_code, 200)
		with zipfile.ZipFile(BytesIO(unlinked_archive_body)) as archive:
			unlinked_names = archive.namelist()
		self.assertEqual(unlinked_names, ["Без привязки к событию/free.png"])

	def test_album_photo_files_are_family_scoped(self):
		family = Family.objects.create(name="Тестовая семья", created_by=self.user)
		other_user = self.user_model.objects.create_user(username="outsider", password=self.password)

		with tempfile.TemporaryDirectory() as media_root, override_settings(MEDIA_ROOT=media_root):
			upload = SimpleUploadedFile("private.png", self._image_bytes(), content_type="image/png")
			photo = FamilyPhoto.objects.create(family=family, image=upload, uploaded_by=self.user)

			self.client.login(username=other_user.username, password=self.password)
			preview = self.client.get(f"/album/photos/{photo.id}/preview/")
			download = self.client.get(f"/album/photos/{photo.id}/download/")

		self.assertEqual(preview.status_code, 404)
		self.assertEqual(download.status_code, 404)

	def _image_bytes(self, size=(8, 8)):
		buffer = BytesIO()
		Image.new("RGB", size, color="white").save(buffer, format="PNG")
		return buffer.getvalue()

	def test_birthday_event_defaults_to_yearly_recurrence(self):
		form = EventForm(
			{
				"title": "День рождения",
				"date": "2020-05-01",
				"kind": "birthday",
				"recurrence": "none",
				"remind_days_before": "0",
			}
		)
		self.assertTrue(form.is_valid(), form.errors)
		self.assertEqual(form.cleaned_data["recurrence"], "yearly")

	def test_weekly_event_next_date(self):
		family = Family.objects.create(name="Тестовая семья", created_by=self.user)
		event = Event.objects.create(
			family=family,
			title="Еженедельный созвон",
			date=timezone.datetime(2026, 5, 11).date(),
			recurrence="weekly",
		)
		self.assertEqual(
			get_next_event_date(event, timezone.datetime(2026, 5, 18).date()),
			timezone.datetime(2026, 5, 18).date(),
		)

	def test_family_tree_rejects_parent_cycle(self):
		family = Family.objects.create(name="Тестовая семья", created_by=self.user)
		parent = FamilyMember.objects.create(family=family, first_name="Родитель")
		child = FamilyMember.objects.create(family=family, first_name="Ребёнок", parent1=parent)

		with self.assertRaises(FamilyTreeValidationError):
			apply_relation_action(family, "set_parent", {"child": parent.id, "parent": child.id})

	def test_family_tree_rejects_duplicate_member(self):
		family = Family.objects.create(name="Тестовая семья", created_by=self.user)
		FamilyMember.objects.create(family=family, first_name="Анна", last_name="Иванова")

		with self.assertRaises(FamilyTreeValidationError):
			apply_relation_action(
				family,
				"create_member",
				{"first_name": "Анна", "last_name": "Иванова"},
			)

	def test_family_tree_reports_one_sided_spouse(self):
		family = Family.objects.create(name="Тестовая семья", created_by=self.user)
		member_a = FamilyMember.objects.create(family=family, first_name="Анна")
		member_b = FamilyMember.objects.create(family=family, first_name="Иван")
		member_a.spouse = member_b
		member_a.save(update_fields=["spouse"])

		issues = validate_family_tree(family)
		self.assertTrue(any(issue.code == "one_sided_spouse" for issue in issues))

	def test_chat_api_supports_replies_and_reactions(self):
		family = Family.objects.create(name="Тестовая семья", created_by=self.user)
		FamilyMembership.objects.create(family=family, user=self.user, role="owner")
		source = Message.objects.create(family=family, sender=self.user, text="Первое")

		self.client.login(username=self.user.username, password=self.password)
		response = self.client.post(
			f"/messages/api/send/?family={family.id}",
			json.dumps({"text": "Ответ", "reply_to": source.id}),
			content_type="application/json",
		)
		self.assertEqual(response.status_code, 200)
		reply = Message.objects.get(text="Ответ")
		self.assertEqual(reply.reply_to_id, source.id)

		response = self.client.post(
			f"/messages/api/reaction/?family={family.id}",
			json.dumps({"message": reply.id, "emoji": "👍"}),
			content_type="application/json",
		)
		self.assertEqual(response.status_code, 200)
		self.assertTrue(MessageReaction.objects.filter(message=reply, user=self.user, emoji="👍").exists())
