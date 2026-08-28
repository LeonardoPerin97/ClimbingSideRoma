from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class AuditLogEntry(models.Model):
    class Action(models.TextChoices):
        CREATE = "create", _("Created")
        UPDATE = "update", _("Updated")
        ARCHIVE = "archive", _("Archived")
        RESTORE = "restore", _("Restored")
        DELETE = "delete", _("Deleted")
        ROLE_CHANGE = "role_change", _("Role changed")
        UPLOAD = "upload", _("Uploaded")
        REPLACE = "replace", _("Replaced")
        ANNOTATE = "annotate", _("Annotated")

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_log_entries",
        verbose_name=_("actor"),
    )
    action = models.CharField(_("action"), max_length=20, choices=Action.choices)
    entity_type = models.CharField(_("entity type"), max_length=50)
    entity_id = models.CharField(_("entity ID"), max_length=64)
    metadata = models.JSONField(_("metadata"), default=dict, blank=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")
        verbose_name = _("audit log entry")
        verbose_name_plural = _("audit log entries")
        indexes = [
            models.Index(fields=("created_at",)),
            models.Index(fields=("entity_type", "entity_id")),
        ]

    def __str__(self) -> str:
        return f"{self.get_action_display()} — {self.entity_type} #{self.entity_id}"
