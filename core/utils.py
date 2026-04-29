from datetime import date as date_type


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


def get_next_event_date(event, today: date_type):
	if event.kind == "birthday" and event.date:
		return next_annual_date(event.date.month, event.date.day, today)
	return event.date