"""Tests for gamification services — badge seeding and awarding."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.gamification.models import Badge, UserBadge
from apps.gamification.services import award, ensure_default_badges

User = get_user_model()


class EnsureDefaultBadgesTests(TestCase):
    def setUp(self):
        import apps.gamification.services as svc
        svc._badges_seeded = False

    def test_creates_all_default_badges(self):
        badges = list(ensure_default_badges())
        codes = {b.code for b in badges}
        self.assertIn("hearth_keeper", codes)
        self.assertIn("family_chef", codes)
        self.assertIn("planner", codes)
        self.assertIn("birthday_buddy", codes)
        self.assertIn("voter", codes)

    def test_idempotent_second_call(self):
        ensure_default_badges()
        count_before = Badge.objects.count()
        ensure_default_badges()
        self.assertEqual(Badge.objects.count(), count_before)

    def test_sets_seeded_flag(self):
        import apps.gamification.services as svc
        svc._badges_seeded = False
        ensure_default_badges()
        self.assertTrue(svc._badges_seeded)

    def test_does_not_overwrite_admin_edits(self):
        Badge.objects.create(code="hearth_keeper", title="Custom Title", description="x", emoji="x")
        import apps.gamification.services as svc
        svc._badges_seeded = False
        ensure_default_badges()
        badge = Badge.objects.get(code="hearth_keeper")
        self.assertEqual(badge.title, "Custom Title")


class AwardTests(TestCase):
    def setUp(self):
        import apps.gamification.services as svc
        svc._badges_seeded = False
        self.user = User.objects.create_user(username="player", password="pass")

    def test_award_creates_user_badge(self):
        result = award(self.user, "hearth_keeper")
        self.assertIsNotNone(result)
        self.assertTrue(UserBadge.objects.filter(user=self.user, badge__code="hearth_keeper").exists())

    def test_award_idempotent(self):
        award(self.user, "hearth_keeper")
        result2 = award(self.user, "hearth_keeper")
        self.assertIsNone(result2)
        self.assertEqual(UserBadge.objects.filter(user=self.user, badge__code="hearth_keeper").count(), 1)

    def test_award_unknown_code_returns_none(self):
        result = award(self.user, "nonexistent_badge_xyz")
        self.assertIsNone(result)

    def test_award_none_user_returns_none(self):
        self.assertIsNone(award(None, "hearth_keeper"))

    def test_award_unauthenticated_user_returns_none(self):
        from unittest.mock import MagicMock
        fake = MagicMock()
        fake.is_authenticated = False
        self.assertIsNone(award(fake, "hearth_keeper"))
