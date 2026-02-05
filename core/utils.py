from calendar import monthrange
from datetime import date as date_type, timedelta


def _safe_date(year: int, month: int, day: int) -> date_type:
	try:
		return date_type(year, month, day)
	except ValueError:
		if month == 2 and day == 29:
			return date_type(year, 2, 28)
		raise


def next_annual_date(month: int, day: int, today: date_type) -> date_type:
	target = _safe_date(today.year, month, day)
	if target < today:
		target = _safe_date(today.year + 1, month, day)
	return target


def _add_months(value: date_type, months: int) -> date_type:
	month_index = value.month - 1 + months
	year = value.year + month_index // 12
	month = month_index % 12 + 1
	day = min(value.day, monthrange(year, month)[1])
	return date_type(year, month, day)


def get_next_event_date(event, today: date_type):
	if not event.date:
		return None
	recurrence = "yearly" if event.kind == "birthday" else getattr(event, "recurrence", "none")
	if recurrence == "yearly":
		return next_annual_date(event.date.month, event.date.day, today)
	if recurrence == "daily":
		return today if event.date <= today else event.date
	if recurrence == "weekly":
		if event.date >= today:
			return event.date
		days_since = (today - event.date).days
		days_until = (7 - days_since % 7) % 7
		return today + timedelta(days=days_until)
	if recurrence == "monthly":
		target = event.date
		while target < today:
			months = (today.year - event.date.year) * 12 + today.month - event.date.month
			target = _add_months(event.date, max(1, months))
			if target < today:
				target = _add_months(target, 1)
		return target
	return event.date
