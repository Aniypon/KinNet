"""Tests for notifications services — in-app notify and notify_many."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.notifications.models import Notification
from apps.notifications.services import notify, notify_many

User = get_user_model()


class NotifyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="recipient", password="pass")

    @patch("apps.notifications.services.pubsub_publish")
    def test_creates_notification_record(self, mock_pub):
        note = notify(self.user, title="Test", body="Hello", kind="system")
        self.assertIsNotNone(note.pk)
        self.assertEqual(note.title, "Test")
        self.assertEqual(note.body, "Hello")
        self.assertEqual(note.kind, "system")
        self.assertEqual(note.user, self.user)

    @patch("apps.notifications.services.pubsub_publish")
    def test_publishes_to_pubsub(self, mock_pub):
        notify(self.user, title="Ping", url="/test/")
        mock_pub.assert_called_once()
        call_args = mock_pub.call_args
        self.assertEqual(call_args[0][0], self.user.id)
        payload = call_args[0][1]
        self.assertEqual(payload["title"], "Ping")
        self.assertEqual(payload["url"], "/test/")

    @patch("apps.notifications.services.pubsub_publish")
    def test_empty_url_defaults_to_slash_in_payload(self, mock_pub):
        notify(self.user, title="No URL")
        payload = mock_pub.call_args[0][1]
        self.assertEqual(payload["url"], "/")

    @patch("apps.notifications.services.pubsub_publish")
    def test_returns_notification_object(self, mock_pub):
        result = notify(self.user, title="x")
        self.assertIsInstance(result, Notification)

    @patch("apps.notifications.services.pubsub_publish")
    def test_notification_is_unread_by_default(self, mock_pub):
        note = notify(self.user, title="Fresh")
        self.assertFalse(note.is_read)


class NotifyManyTests(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(username="u1", password="pass")
        self.user2 = User.objects.create_user(username="u2", password="pass")

    @patch("apps.notifications.services.pubsub_publish")
    def test_empty_users_returns_zero(self, mock_pub):
        count = notify_many([], title="x")
        self.assertEqual(count, 0)
        mock_pub.assert_not_called()

    @patch("apps.notifications.services.pubsub_publish")
    def test_creates_notifications_for_all_users(self, mock_pub):
        count = notify_many([self.user1, self.user2], title="Broadcast", kind="event")
        self.assertEqual(count, 2)
        self.assertEqual(Notification.objects.filter(title="Broadcast").count(), 2)

    @patch("apps.notifications.services.pubsub_publish")
    def test_publishes_per_user(self, mock_pub):
        notify_many([self.user1, self.user2], title="Multi")
        self.assertEqual(mock_pub.call_count, 2)
        notified_ids = {call[0][0] for call in mock_pub.call_args_list}
        self.assertIn(self.user1.id, notified_ids)
        self.assertIn(self.user2.id, notified_ids)

    @patch("apps.notifications.services.pubsub_publish")
    def test_single_user_works(self, mock_pub):
        count = notify_many([self.user1], title="Solo")
        self.assertEqual(count, 1)
