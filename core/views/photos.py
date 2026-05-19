"""Family photo album upload/download/preview."""

from __future__ import annotations

import os
import zipfile
from datetime import timedelta
from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from PIL import Image, ImageOps

from ..family_context import current_family
from ..forms import FamilyPhotoForm
from ..models import FamilyPhoto
from ._helpers import album_archive_path, get_family_photo_for_user, has_family_access  # noqa: F401


@login_required
def family_album(request):
	family, families = current_family(request)
	if not family:
		return redirect("families")
	for expired_photo in family.photos.filter(created_at__lte=timezone.now() - timedelta(days=7)):
		if expired_photo.image:
			expired_photo.image.delete(save=False)
		expired_photo.delete()

	if request.method == "POST":
		form = FamilyPhotoForm(request.POST, request.FILES, family=family)
		if form.is_valid():
			for image in form.cleaned_data["images"]:
				FamilyPhoto.objects.create(
					family=family,
					event=form.cleaned_data["event"],
					image=image,
					caption=form.cleaned_data["caption"],
					uploaded_by=request.user,
				)
			return redirect(f"{request.path}?family={family.id}")
	else:
		form = FamilyPhotoForm(family=family)

	photos = list(family.photos.select_related("uploaded_by", "event"))
	event_albums = {}
	unlinked_album = {
		"title": "Без привязки к событию",
		"event": None,
		"photos": [],
	}
	for photo in photos:
		if photo.event_id:
			album = event_albums.setdefault(
				photo.event_id,
				{
					"title": photo.event.title,
					"event": photo.event,
					"photos": [],
				},
			)
			album["photos"].append(photo)
		else:
			unlinked_album["photos"].append(photo)

	albums = list(event_albums.values())
	if unlinked_album["photos"]:
		albums.append(unlinked_album)

	return render(
		request,
		"family_album.html",
		{"form": form, "albums": albums, "photos": photos, "family": family, "families": families},
	)


@login_required
def family_album_download(request):
	family, _families = current_family(request)
	if not family:
		return HttpResponse(status=404)

	for expired_photo in family.photos.filter(created_at__lte=timezone.now() - timedelta(days=7)):
		if expired_photo.image:
			expired_photo.image.delete(save=False)
		expired_photo.delete()

	event_id = request.GET.get("event")
	unlinked = request.GET.get("unlinked") == "1"
	photos_query = family.photos.select_related("event")
	if unlinked:
		photos_query = photos_query.filter(event__isnull=True)
	elif event_id:
		photos_query = photos_query.filter(event_id=event_id)
	else:
		return HttpResponse(status=404)

	photos = list(photos_query.order_by("created_at"))
	if not photos:
		return HttpResponse(status=404)

	archive = BytesIO()
	used_paths = set()
	with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
		for photo in photos:
			if not photo.image:
				continue
			with photo.image.open("rb") as image_file:
				zip_file.writestr(album_archive_path(photo, used_paths), image_file.read())
	archive.seek(0)

	if unlinked:
		filename = f"family-album-{family.id}-unlinked.zip"
	else:
		filename = f"family-album-{family.id}-event-{event_id}.zip"
	return FileResponse(archive, as_attachment=True, filename=filename, content_type="application/zip")


@login_required
def family_photo_download(request, photo_id):
	photo = get_family_photo_for_user(request.user, photo_id)
	if photo is None:
		return HttpResponse(status=404)

	filename = os.path.basename(photo.image.name) or f"family-photo-{photo.id}"
	return FileResponse(photo.image.open("rb"), as_attachment=True, filename=filename)


@login_required
def family_photo_preview(request, photo_id):
	photo = get_family_photo_for_user(request.user, photo_id)
	if photo is None:
		return HttpResponse(status=404)

	with photo.image.open("rb") as image_file:
		with Image.open(image_file) as source:
			image = ImageOps.exif_transpose(source)
			if image.mode not in ("RGB", "L"):
				image = image.convert("RGB")
			image.thumbnail((560, 560), Image.Resampling.LANCZOS)
			buffer = BytesIO()
			image.save(buffer, format="JPEG", quality=68, optimize=True)

	response = HttpResponse(buffer.getvalue(), content_type="image/jpeg")
	response["Cache-Control"] = "private, max-age=3600"
	return response
