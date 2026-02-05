"""Template tags for role-based UI gating in KinNet templates."""

from django import template
from django.template import NodeList

from core.permissions import has_role as _has_role

register = template.Library()


class RoleGateNode(template.Node):
    def __init__(self, roles, nodelist):
        self.roles = roles
        self.nodelist = nodelist

    def render(self, context):
        request = context.get("request")
        family = context.get("active_family")
        if request is None or family is None:
            return ""
        if not request.user.is_authenticated:
            return ""
        if _has_role(request.user, family, self.roles):
            return self.nodelist.render(context)
        return ""


@register.tag("role_gate")
def role_gate(parser, token):
    """Render inner block only when user has one of the given roles.

    Usage::

        {% role_gate "owner,admin" %}
          <button>Редактировать</button>
        {% endrole_gate %}
    """
    try:
        tag_name, roles_arg = token.split_contents()
    except ValueError:
        raise template.TemplateSyntaxError(
            f"{token.split_contents()[0]} requires exactly one argument (comma-separated roles)"
        )
    roles_str = roles_arg.strip("\"'")
    roles = [r.strip() for r in roles_str.split(",") if r.strip()]
    nodelist = parser.parse(("endrole_gate",))
    parser.delete_first_token()
    return RoleGateNode(roles, nodelist)
