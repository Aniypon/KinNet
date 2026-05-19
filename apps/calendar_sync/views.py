"""ICS calendar feed generation."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, time, timedelta, timezone as dt_timezone

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from core.family_context import get_user_families as _user_families
from core.models import Event, Family

from .models import CalendarFeedToken

User = get_user_model()


def _occurrences_for_year(event: Event, year: int) -> list[date]:
    """Return concrete dates around the exported year for recurring events."""
    recurrence = "yearly" if event.kind == "birthday" else event.recurrence
    if recurrence == "yearly":
        occurrences: list[date] = []
        for y in (year, year + 1):
            try:
                occurrences.append(event.date.replace(year=y))
            except ValueError:
                # Feb 29 fallback for non-leap years; leap years keep Feb 29.
                occurrences.append(date(y, event.date.month, 28))
        return occurrences
    if recurrence == "monthly":
        return [
            date(y, month, min(event.date.day, monthrange(y, month)[1]))
            for y in (year, year + 1)
            for month in range(1, 13)
        ]
    if recurrence == "weekly":
        start = date(year, 1, 1)
        first = start + timedelta(days=(event.date.weekday() - start.weekday()) % 7)
        occurrences = []
        current = first
        end = date(year + 1, 12, 31)
        while current <= end:
            if current >= event.date:
                occurrences.append(current)
            current += timedelta(days=7)
        return occurrences
    if recurrence == "daily":
        start = max(event.date, date(year, 1, 1))
        end = date(year + 1, 12, 31)
        occurrences = []
        current = start
        while current <= end:
            occurrences.append(current)
            current += timedelta(days=1)
        return occurrences
    return [event.date]


def _ics_escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(",", "\\,")
        .replace(";", "\\;")
        .replace("\n", "\\n")
    )


@login_required
def feed_settings(request):
    token, _ = CalendarFeedToken.objects.get_or_create(user=request.user)
    feed_url = request.build_absolute_uri(
        reverse("calendar_sync:ics_feed", args=[token.token])
    )
    if request.method == "POST" and request.POST.get("rotate"):
        token.delete()
        token = CalendarFeedToken.objects.create(user=request.user)
        feed_url = request.build_absolute_uri(
            reverse("calendar_sync:ics_feed", args=[token.token])
        )
    return render(
        request,
        "calendar_sync/settings.html",
        {"token": token, "feed_url": feed_url},
    )


def ics_feed(request, token: str):
    feed_token = get_object_or_404(CalendarFeedToken, token=token)
    user = feed_token.user
    families = Family.objects.filter(
        Q(memberships__user=user) | Q(created_by=user)
    ).distinct()
    events = Event.objects.filter(family__in=families).select_related("family", "member")

    now = datetime.now(dt_timezone.utc)
    year = now.year

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//KinNet//Family Calendar//RU",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_ics_escape('KinNet — ' + (user.get_full_name() or user.username))}",
    ]
    for event in events:
        for occurrence in _occurrences_for_year(event, year):
            uid = f"kinnet-{event.id}-{occurrence:%Y%m%d}@kinnet"
            start = datetime.combine(occurrence, time(9, 0), dt_timezone.utc)
            end = start + timedelta(hours=1)
            lines.extend(
                [
                    "BEGIN:VEVENT",
                    f"UID:{uid}",
                    f"DTSTAMP:{now:%Y%m%dT%H%M%SZ}",
                    f"DTSTART:{start:%Y%m%dT%H%M%SZ}",
                    f"DTEND:{end:%Y%m%dT%H%M%SZ}",
                    f"SUMMARY:{_ics_escape(event.title)}",
                    f"DESCRIPTION:{_ics_escape(event.description or event.family.name)}",
                    "END:VEVENT",
                ]
            )
    lines.append("END:VCALENDAR")

    response = HttpResponse("\r\n".join(lines), content_type="text/calendar; charset=utf-8")
    response["Content-Disposition"] = 'inline; filename="kinnet.ics"'
    return response
