"""Tests for budget app — expense and wishlist views."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.models import Family, FamilyMember, FamilyMembership
from apps.budget.models import Expense, WishlistItem, Wishlist

User = get_user_model()


class ExpenseViewTests(TestCase):
    def setUp(self):
        self.password = "TestPass12345"
        self.user = User.objects.create_user(username="owner", password=self.password, first_name="Owner")
        self.family = Family.objects.create(name="Test Family", created_by=self.user)
        FamilyMembership.objects.create(family=self.family, user=self.user, role="owner")
        self.client.login(username="owner", password=self.password)

    def test_expense_list_requires_login(self):
        self.client.logout()
        response = self.client.get(f"/budget/?family={self.family.id}")
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response["Location"])

    def test_expense_list_renders(self):
        response = self.client.get(f"/budget/?family={self.family.id}")
        self.assertEqual(response.status_code, 200)

    def test_expense_list_period_filter(self):
        for period in ("month", "prev", "3m", "year", "all"):
            response = self.client.get(f"/budget/?family={self.family.id}&period={period}")
            self.assertEqual(response.status_code, 200, f"period={period} failed")

    def test_expense_list_invalid_period_defaults_to_month(self):
        response = self.client.get(f"/budget/?family={self.family.id}&period=invalid")
        self.assertEqual(response.status_code, 200)

    def test_expense_create_renders(self):
        response = self.client.get(f"/budget/new/?family={self.family.id}")
        self.assertEqual(response.status_code, 200)

    def test_expense_create_post(self):
        response = self.client.post(
            f"/budget/new/?family={self.family.id}",
            {
                "title": "Продукты",
                "amount": "500.00",
                "spent_on": timezone.localdate().isoformat(),
                "category": "Еда",
                "payer": self.user.id,
                "split_mode": "solo",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Expense.objects.filter(family=self.family, title="Продукты").exists())

    def test_expense_edit_renders(self):
        expense = Expense.objects.create(
            family=self.family, payer=self.user, title="X", amount=Decimal("100"), spent_on=timezone.localdate()
        )
        response = self.client.get(f"/budget/{expense.id}/edit/?family={self.family.id}")
        self.assertEqual(response.status_code, 200)

    def test_expense_delete(self):
        expense = Expense.objects.create(
            family=self.family, payer=self.user, title="Delete me", amount=Decimal("50"), spent_on=timezone.localdate()
        )
        response = self.client.post(
            f"/budget/{expense.id}/delete/?family={self.family.id}", follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Expense.objects.filter(id=expense.id).exists())

    def test_expense_list_shows_expenses(self):
        Expense.objects.create(
            family=self.family, payer=self.user, title="Аренда", amount=Decimal("1000"), spent_on=timezone.localdate()
        )
        response = self.client.get(f"/budget/?family={self.family.id}")
        self.assertContains(response, "Аренда")


class WishlistViewTests(TestCase):
    def setUp(self):
        self.password = "TestPass12345"
        self.user = User.objects.create_user(username="wisher", password=self.password, first_name="Wisher")
        self.family = Family.objects.create(name="Wish Family", created_by=self.user)
        FamilyMembership.objects.create(family=self.family, user=self.user, role="owner")
        self.member = FamilyMember.objects.create(
            family=self.family, first_name="Wisher", user=self.user
        )
        self.client.login(username="wisher", password=self.password)

    def test_wishlist_list_renders(self):
        response = self.client.get(f"/budget/wishlists/?family={self.family.id}")
        self.assertEqual(response.status_code, 200)


    def test_wishlist_item_reserved_property(self):
        wishlist = Wishlist.objects.create(
            family=self.family, owner_member=self.member, created_by=self.user
        )
        item = WishlistItem.objects.create(wishlist=wishlist, title="Книга")
        self.assertFalse(item.is_reserved)
        item.reserved_by = self.user
        self.assertTrue(item.is_reserved)


class BudgetModelsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", password="p")
        self.family = Family.objects.create(name="F", created_by=self.user)

    def test_expense_str(self):
        e = Expense(title="Groceries", amount=Decimal("123.45"))
        self.assertIn("Groceries", str(e))
        self.assertIn("123.45", str(e))

    def test_wishlist_item_str(self):
        item = WishlistItem(title="Bicycle")
        self.assertEqual(str(item), "Bicycle")
