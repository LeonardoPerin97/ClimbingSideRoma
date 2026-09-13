from typing import Any

from django.db.models.signals import post_delete, post_migrate
from django.dispatch import receiver

from .media_services import schedule_profile_image_file_deletion
from .models import User
from .roles import sync_role_permissions


@receiver(post_migrate, dispatch_uid="accounts.sync_role_permissions")
def configure_role_permissions(**kwargs: Any) -> None:
    del kwargs
    sync_role_permissions()


@receiver(post_delete, sender=User, dispatch_uid="accounts.delete_profile_image_file")
def delete_profile_image_file(sender: type[User], instance: User, **kwargs: Any) -> None:
    del sender, kwargs
    stored_name = instance.profile_image.name
    if stored_name:
        schedule_profile_image_file_deletion(instance.profile_image.storage, stored_name)
