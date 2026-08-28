from enum import StrEnum

from django.contrib.auth.models import Group, Permission
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from .models import User


class Role(StrEnum):
    USER = "User"
    ROUTE_SETTER = "RouteSetter"
    ADMIN = "Admin"


ROLE_CHOICES = (
    (Role.USER, _("User")),
    (Role.ROUTE_SETTER, _("Route setter")),
    (Role.ADMIN, _("Administrator")),
)
ROLE_GROUP_NAMES = {role.value for role in Role}

USER_PERMISSION_CODENAMES = {
    "add_ascent",
    "change_ascent",
    "delete_ascent",
    "view_ascent",
}

ROUTE_SETTER_PERMISSION_CODENAMES = USER_PERMISSION_CODENAMES | {
    "view_wall",
    "add_climbingroute",
    "change_climbingroute",
    "view_climbingroute",
    "add_routeimage",
    "change_routeimage",
    "view_routeimage",
}


def role_for(user: User) -> Role:
    if user.is_superuser or user.groups.filter(name=Role.ADMIN).exists():
        return Role.ADMIN
    if user.groups.filter(name=Role.ROUTE_SETTER).exists():
        return Role.ROUTE_SETTER
    return Role.USER


def role_label_for(user: User) -> str:
    return str(dict(ROLE_CHOICES)[role_for(user)])


@transaction.atomic
def assign_role(user: User, role: Role) -> None:
    groups = {name: Group.objects.get_or_create(name=name)[0] for name in ROLE_GROUP_NAMES}
    user.groups.remove(*groups.values())
    user.groups.add(groups[role.value])

    should_be_staff = role is Role.ADMIN or user.is_superuser
    if user.is_staff != should_be_staff:
        user.is_staff = should_be_staff
        user.save(update_fields=["is_staff"])


@transaction.atomic
def sync_role_permissions() -> None:
    groups = {name: Group.objects.get_or_create(name=name)[0] for name in ROLE_GROUP_NAMES}
    groups[Role.USER].permissions.set(
        Permission.objects.filter(codename__in=USER_PERMISSION_CODENAMES)
    )
    groups[Role.ROUTE_SETTER].permissions.set(
        Permission.objects.filter(codename__in=ROUTE_SETTER_PERMISSION_CODENAMES)
    )
    groups[Role.ADMIN].permissions.set(Permission.objects.all())
