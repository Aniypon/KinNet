import json
import os
from pathlib import Path

from django import template
from django.conf import settings
from django.templatetags.static import static
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def vite_asset(entry):
    dev_server = os.environ.get("VITE_DEV_SERVER")
    dev_origin = os.environ.get("VITE_DEV_ORIGIN", "http://localhost:5173")
    if settings.DEBUG and dev_server in {"1", "true", "on"}:
        return format_html(
            '<script type="module" src="{}/@vite/client"></script>'
            '<script type="module" src="{}/{}"></script>',
            dev_origin.rstrip("/"),
            dev_origin.rstrip("/"),
            entry.lstrip("/"),
        )

    manifest_path = Path(settings.BASE_DIR) / "static" / "dist" / ".vite" / "manifest.json"
    if not manifest_path.exists():
        return mark_safe("")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    asset = manifest.get(entry)
    if not asset:
        return mark_safe("")

    tags = []
    for css_file in asset.get("css", []):
        tags.append(f'<link rel="stylesheet" href="{static("dist/" + css_file)}" />')
    tags.append(f'<script type="module" src="{static("dist/" + asset["file"])}"></script>')
    return mark_safe("".join(tags))
