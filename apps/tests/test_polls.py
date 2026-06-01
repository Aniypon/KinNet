"""Tests for polls app — models, voting, and views."""
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.models import Family, FamilyMembership
from apps.polls.models import Poll, PollChoice, PollVote

User = get_user_model()


class PollModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="pollster", password="pass")
        self.family = Family.objects.create(name="Poll Family", created_by=self.user)

    def test_effectively_closed_when_flag_set(self):
        poll = Poll.objects.create(family=self.family, author=self.user, question="Q?", is_closed=True)
        self.assertTrue(poll.effectively_closed)

    def test_effectively_closed_when_past_close_time(self):
        past = timezone.now() - timedelta(hours=1)
        poll = Poll.objects.create(family=self.family, author=self.user, question="Q?", closes_at=past)
        self.assertTrue(poll.effectively_closed)

    def test_not_closed_when_open_and_future_close(self):
        future = timezone.now() + timedelta(hours=1)
        poll = Poll.objects.create(family=self.family, author=self.user, question="Q?", closes_at=future)
        self.assertFalse(poll.effectively_closed)

    def test_not_closed_when_no_close_time(self):
        poll = Poll.objects.create(family=self.family, author=self.user, question="Q?")
        self.assertFalse(poll.effectively_closed)

    def test_poll_str(self):
        poll = Poll(question="Куда едем?")
        self.assertEqual(str(poll), "Куда едем?")

    def test_choice_str(self):
        choice = PollChoice(text="Море")
        self.assertEqual(str(choice), "Море")


class PollViewTests(TestCase):
    def setUp(self):
        self.password = "TestPass12345"
        self.user = User.objects.create_user(username="voter", password=self.password)
        self.family = Family.objects.create(name="Vote Family", created_by=self.user)
        FamilyMembership.objects.create(family=self.family, user=self.user, role="owner")
        self.client.login(username="voter", password=self.password)

    def test_poll_list_renders(self):
        response = self.client.get(f"/polls/?family={self.family.id}")
        self.assertEqual(response.status_code, 200)

    def test_poll_create_renders(self):
        response = self.client.get(f"/polls/new/?family={self.family.id}")
        self.assertEqual(response.status_code, 200)

    def test_poll_create_post(self):
        response = self.client.post(
            f"/polls/new/?family={self.family.id}",
            {
                "question": "Что на ужин?",
                "description": "",
                "allow_multiple": False,
                "choice_0": "Пицца",
                "choice_1": "Суши",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Poll.objects.filter(family=self.family, question="Что на ужин?").exists())

    def test_voting_on_poll(self):
        poll = Poll.objects.create(family=self.family, author=self.user, question="Куда?")
        choice = PollChoice.objects.create(poll=poll, text="Парк")
        response = self.client.post(
            f"/polls/{poll.id}/vote/?family={self.family.id}",
            {"choice": [str(choice.id)]},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(PollVote.objects.filter(choice=choice, user=self.user).exists())

    def test_vote_replaces_previous_vote(self):
        poll = Poll.objects.create(family=self.family, author=self.user, question="Vote?")
        choice1 = PollChoice.objects.create(poll=poll, text="A")
        choice2 = PollChoice.objects.create(poll=poll, text="B")
        # First vote
        self.client.post(
            f"/polls/{poll.id}/vote/?family={self.family.id}",
            {"choice": [str(choice1.id)]},
            follow=True,
        )
        # Second vote on same poll — replaces first
        self.client.post(
            f"/polls/{poll.id}/vote/?family={self.family.id}",
            {"choice": [str(choice2.id)]},
            follow=True,
        )
        self.assertFalse(PollVote.objects.filter(choice=choice1, user=self.user).exists())
        self.assertTrue(PollVote.objects.filter(choice=choice2, user=self.user).exists())

    def test_vote_on_closed_poll_rejected(self):
        poll = Poll.objects.create(family=self.family, author=self.user, question="Closed?", is_closed=True)
        choice = PollChoice.objects.create(poll=poll, text="Yes")
        response = self.client.post(
            f"/polls/{poll.id}/vote/?family={self.family.id}",
            {"choice": [str(choice.id)]},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PollVote.objects.filter(choice=choice, user=self.user).exists())
