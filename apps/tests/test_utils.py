"""Tests for core/utils.py — date utilities used across the project."""
from datetime import date, datetime

from django.test import TestCase

from core.utils import (
    _add_months,
    _safe_date,
    get_next_event_date,
    next_annual_date,
    parse_local_datetime,
)


class ParseLocalDatetimeTests(TestCase):
    def test_russian_datetime_format(self):
        result = parse_local_datetime("25.12.2025 14:30")
        self.assertEqual(result, datetime(2025, 12, 25, 14, 30))

    def test_russian_date_only(self):
        result = parse_local_datetime("01.06.2026")
        self.assertEqual(result, datetime(2026, 6, 1, 0, 0))

    def test_slash_date_format(self):
        result = parse_local_datetime("31/12/2025")
        self.assertEqual(result, datetime(2025, 12, 31, 0, 0))

    def test_slash_datetime_format(self):
        result = parse_local_datetime("15/03/2024 09:00")
        self.assertEqual(result, datetime(2024, 3, 15, 9, 0))

    def test_iso_format_fallback(self):
        result = parse_local_datetime("2026-06-01T10:00:00")
        self.assertIsNotNone(result)

    def test_empty_string_returns_none(self):
        self.assertIsNone(parse_local_datetime(""))
        self.assertIsNone(parse_local_datetime(None))

    def test_whitespace_returns_none(self):
        self.assertIsNone(parse_local_datetime("   "))


class SafeDateTests(TestCase):
    def test_normal_date(self):
        self.assertEqual(_safe_date(2026, 3, 15), date(2026, 3, 15))

    def test_leap_day_on_non_leap_year(self):
        result = _safe_date(2025, 2, 29)
        self.assertEqual(result, date(2025, 2, 28))

    def test_leap_day_on_leap_year(self):
        result = _safe_date(2024, 2, 29)
        self.assertEqual(result, date(2024, 2, 29))


class NextAnnualDateTests(TestCase):
    def test_upcoming_this_year(self):
        today = date(2026, 1, 1)
        result = next_annual_date(6, 15, today)
        self.assertEqual(result, date(2026, 6, 15))

    def test_already_passed_this_year(self):
        today = date(2026, 6, 16)
        result = next_annual_date(6, 15, today)
        self.assertEqual(result, date(2027, 6, 15))

    def test_today_returns_today(self):
        today = date(2026, 6, 1)
        result = next_annual_date(6, 1, today)
        self.assertEqual(result, date(2026, 6, 1))


class AddMonthsTests(TestCase):
    def test_simple_add(self):
        self.assertEqual(_add_months(date(2026, 1, 15), 1), date(2026, 2, 15))

    def test_year_rollover(self):
        self.assertEqual(_add_months(date(2026, 11, 1), 3), date(2027, 2, 1))

    def test_clamps_to_month_end(self):
        result = _add_months(date(2026, 1, 31), 1)
        self.assertEqual(result, date(2026, 2, 28))


class GetNextEventDateTests(TestCase):
    def _make_event(self, **kwargs):
        class FakeEvent:
            date = None
            kind = "custom"
            recurrence = "none"
        obj = FakeEvent()
        for k, v in kwargs.items():
            setattr(obj, k, v)
        return obj

    def test_no_date_returns_none(self):
        event = self._make_event(date=None)
        self.assertIsNone(get_next_event_date(event, date(2026, 6, 1)))

    def test_birthday_forces_yearly(self):
        event = self._make_event(date=date(2000, 6, 15), kind="birthday", recurrence="none")
        today = date(2026, 6, 1)
        self.assertEqual(get_next_event_date(event, today), date(2026, 6, 15))

    def test_yearly_recurrence(self):
        event = self._make_event(date=date(2020, 12, 25), kind="custom", recurrence="yearly")
        today = date(2026, 12, 26)
        self.assertEqual(get_next_event_date(event, today), date(2027, 12, 25))

    def test_daily_recurrence_returns_today(self):
        event = self._make_event(date=date(2020, 1, 1), kind="custom", recurrence="daily")
        today = date(2026, 6, 1)
        self.assertEqual(get_next_event_date(event, today), today)

    def test_daily_recurrence_future_event(self):
        future = date(2027, 1, 1)
        event = self._make_event(date=future, kind="custom", recurrence="daily")
        today = date(2026, 6, 1)
        self.assertEqual(get_next_event_date(event, today), future)

    def test_weekly_recurrence_same_day(self):
        event = self._make_event(date=date(2026, 5, 18), kind="custom", recurrence="weekly")
        today = date(2026, 5, 25)
        self.assertEqual(get_next_event_date(event, today), date(2026, 5, 25))

    def test_weekly_recurrence_between_weeks(self):
        event = self._make_event(date=date(2026, 5, 11), kind="custom", recurrence="weekly")
        today = date(2026, 5, 14)
        # Monday, event was on Monday — next occurrence Monday 5/18
        self.assertEqual(get_next_event_date(event, today), date(2026, 5, 18))

    def test_monthly_recurrence(self):
        event = self._make_event(date=date(2026, 1, 15), kind="custom", recurrence="monthly")
        today = date(2026, 6, 1)
        result = get_next_event_date(event, today)
        self.assertGreaterEqual(result, today)
        self.assertEqual(result.day, 15)

    def test_no_recurrence_returns_original_date(self):
        event_date = date(2025, 1, 1)
        event = self._make_event(date=event_date, kind="custom", recurrence="none")
        self.assertEqual(get_next_event_date(event, date(2026, 6, 1)), event_date)
