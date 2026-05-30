from __future__ import annotations

from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from ..family_context import current_family, get_user_families
from ..forms import SignupForm, UserProfileForm
from ..models import FamilyInvitation, UserProfile
from ..utils import get_next_event_date
from ._helpers import sync_birthday_events

def home(request):
    family = families = None
    pending_invitations = upcoming_events = upcoming_tasks = []
    unread_notifications = []
    unread_notifications_count = 0
    latest_message = None
    today_feed = global_results = onboarding_steps = []
    if request.user.is_authenticated:
        family, families = current_family(request)
        from apps.notifications.models import Notification
        # Один запрос для списка и счётчика: грузим до 100 непрочитанных, срезаем для отображения
        _all_unread = list(Notification.objects.filter(user=request.user, is_read=False)[:100])
        unread_notifications = _all_unread[:5]
        unread_notifications_count = len(_all_unread)
        pending_invitations = FamilyInvitation.objects.filter(status="pending", username=request.user.username)
        if family:
            today = timezone.localdate()
            events = list(family.events.select_related("member"))
            for event in events:
                event.next_date = get_next_event_date(event, today)
            upcoming_events = sorted([e for e in events if e.next_date and e.next_date >= today], key=lambda e: e.next_date)[:3]
            upcoming_tasks = list(family.tasks.filter(status__in=["todo", "in_progress"], due_date__isnull=False).order_by("due_date")[:3])
            latest_message = family.messages.order_by("-created_at").select_related("sender").first()
            recent_messages = list(family.messages.select_related("sender").order_by("-created_at")[:3])
            today_feed = (
                [{"kind": "event", "title": e.title, "meta": e.next_date, "url": f"/events/{e.id}/"} for e in upcoming_events[:2]]
                + [{"kind": "task", "title": t.title, "meta": t.due_date, "url": f"/tasks/{t.id}/"} for t in upcoming_tasks[:2]]
                + [{"kind": "message", "title": m.sender.get_full_name() or m.sender.username, "meta": m.text[:120], "url": f"/messages/?family={family.id}"} for m in recent_messages]
            )
            onboarding_steps = [
                {"label": "Создать семью", "done": bool(family), "url": "/families/"},
                {"label": "Добавить 3 родственников", "done": family.family_members.count() >= 3, "url": f"/members/?family={family.id}&view=add#member-form"},
                {"label": "Собрать первые связи", "done": family.family_members.filter(in_tree=True).count() >= 3, "url": f"/members/?family={family.id}&view=tree&mode=edit"},
                {"label": "Пригласить близкого", "done": family.invitations.exists() or family.memberships.count() > 1, "url": f"/families/{family.id}/"},
            ]
            query = request.GET.get("q", "").strip()
            if query:
                global_results = (
                    [{"kind": "Родственник", "title": str(m), "url": f"/members/{m.id}/"} for m in family.family_members.filter(Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(relation__icontains=query))[:5]]
                    + [{"kind": "Событие", "title": e.title, "url": f"/events/{e.id}/"} for e in family.events.filter(Q(title__icontains=query) | Q(description__icontains=query))[:5]]
                    + [{"kind": "Задача", "title": t.title, "url": f"/tasks/{t.id}/"} for t in family.tasks.filter(Q(title__icontains=query) | Q(description__icontains=query))[:5]]
                    + [{"kind": "Сообщение", "title": m.text[:80], "url": f"/messages/?family={family.id}"} for m in family.messages.filter(text__icontains=query).select_related("sender")[:5]]
                )
    return render(request, "home.html", {
        "family": family, "families": families, "pending_invitations": pending_invitations,
        "upcoming_events": upcoming_events, "upcoming_tasks": upcoming_tasks,
        "latest_message": latest_message, "today_feed": today_feed, "global_results": global_results,
        "search_query": request.GET.get("q", "").strip(),
        "onboarding_steps": onboarding_steps,
        "next_onboarding_step": next((s for s in onboarding_steps if not s["done"]), None),
        "unread_notifications": unread_notifications,
        "unread_notifications_count": unread_notifications_count,
    })

def signup(request):
    form = SignupForm(request.POST) if request.method == "POST" else SignupForm()
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("home")
    return render(request, "registration/signup.html", {"form": form})

@login_required
def profile_edit(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user, defaults={"birth_date": timezone.localdate()})
    if request.method == "POST":
        form = UserProfileForm(request.POST, request.FILES, instance=profile, user=request.user)
        if form.is_valid():
            profile = form.save()
            sync_birthday_events(request.user, profile.birth_date)
            return redirect("profile_edit")
    else:
        form = UserProfileForm(instance=profile, user=request.user)
    return render(request, "entity_form.html", {"form": form, "title": "Мои данные"})

@login_required
def set_active_family(request):
    if request.method != "POST":
        return HttpResponse(status=405)
    family_id = request.POST.get("family_id")
    if family_id and get_user_families(request.user).filter(id=family_id).exists():
        request.session["active_family_id"] = int(family_id)
        request.session.modified = True
    referer = request.META.get("HTTP_REFERER", "/")
    if not url_has_allowed_host_and_scheme(referer, allowed_hosts={request.get_host()}):
        referer = "/"
    parts = urlsplit(referer)
    query = parse_qs(parts.query, keep_blank_values=True)
    query.pop("family", None)
    return redirect(urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query, doseq=True), parts.fragment)) or "/")

def ui_set_pref(request):
    if request.method != "POST":
        return HttpResponse(status=405)
    if "elder" in request.POST:
        request.session["elder_mode"] = request.POST.get("elder") in {"1", "true", "on"}
    if "theme" in request.POST:
        theme = request.POST.get("theme") or "light"
        request.session["theme"] = theme if theme in {"light", "dark"} else "light"
    request.session.modified = True
    return redirect(request.META.get("HTTP_REFERER", "/"))
