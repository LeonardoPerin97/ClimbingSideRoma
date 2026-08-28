from typing import Any

from django.db.models.signals import post_migrate
from django.dispatch import receiver

from .roles import sync_role_permissions


@receiver(post_migrate, dispatch_uid="accounts.sync_role_permissions")
def configure_role_permissions(**kwargs: Any) -> None:
    del kwargs
    sync_role_permissions()
