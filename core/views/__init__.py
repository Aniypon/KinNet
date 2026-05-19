"""core.views — split into domain submodules.

Re-exports every public view callable so legacy ``from core.views import X``
imports (notably ``core/urls.py``) keep working unchanged.
"""

from .home import home, signup, profile_edit, set_active_family, ui_set_pref
from .family import (
	families,
	family_edit,
	family_delete,
	family_leave,
	family_detail,
	family_member_remove,
	invitation_accept,
	invitation_revoke,
	user_suggest,
	user_detail,
)
from .members import (
	family_members,
	member_detail,
	member_edit,
	member_delete,
	family_tree,
	family_tree_edit,
	family_tree_edit_legacy,
	family_tree_order_update,
	family_tree_relations_update,
	family_tree_graph,
)
from .events import events, event_detail, event_edit, event_delete
from .tasks import tasks, task_detail, task_edit, task_delete
from .goals import goals, goal_detail
from .photos import (
	family_album,
	family_album_download,
	family_photo_download,
	family_photo_preview,
)
from .messages import (
	messages,
	messages_api,
	message_send_api,
	message_pin_api,
	message_reaction_api,
	message_typing_api,
	message_delete,
)

__all__ = [
	"home", "signup", "profile_edit", "set_active_family", "ui_set_pref",
	"families", "family_edit", "family_delete", "family_leave", "family_detail",
	"family_member_remove", "invitation_accept", "invitation_revoke",
	"user_suggest", "user_detail",
	"family_members", "member_detail", "member_edit", "member_delete",
	"family_tree", "family_tree_edit", "family_tree_edit_legacy",
	"family_tree_order_update", "family_tree_relations_update", "family_tree_graph",
	"events", "event_detail", "event_edit", "event_delete",
	"tasks", "task_detail", "task_edit", "task_delete",
	"goals", "goal_detail",
	"family_album", "family_album_download", "family_photo_download", "family_photo_preview",
	"messages", "messages_api", "message_send_api", "message_pin_api",
	"message_reaction_api", "message_typing_api", "message_delete",
]
