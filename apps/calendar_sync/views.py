"""ICS calendar feed generation."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone as dt_timezone

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from core.models import Event, Family

from .models import CalendarFeedToken

User = get_user_model()


def _user_families(user):
    return Family.objects.filter(
        Q(memberships__user=user) | Q(created_by=user)
    ).distinct()


def _occurrences_for_year(event: Event, year: int) -> list[date]:
    """Birthdays repeat yearly; everything else is a single date."""
    if event.kind == "birthday":
        occurrences: list[date] = []
        for y in (year, year + 1):
            try:
                occurrences.append(event.date.replace(year=y))
            except ValueError:
                # Feb 29 fallback for non-leap years; leap years keep Feb 29.
                occurrences.append(date(y, event.date.month, 28))
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
        f"X-WR-CALNAME:KinNet — {user.get_full_name() or user.username}",
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
