from typing import Any

from django.db import migrations, models


ROLE_NAMES = ("User", "RouteSetter", "Admin")


def create_role_groups(apps: Any, schema_editor: Any) -> None:
    del schema_editor
    group_model = apps.get_model("auth", "Group")
    for name in ROLE_NAMES:
        group_model.objects.get_or_create(name=name)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="LoginAttempt",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("identifier_hash", models.CharField(max_length=64, unique=True)),
                ("failures", models.PositiveSmallIntegerField(default=0)),
                ("first_failed_at", models.DateTimeField()),
                ("locked_until", models.DateTimeField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "login attempt",
                "verbose_name_plural": "login attempts",
            },
        ),
        migrations.AddField(
            model_name="user",
            name="email_verified_at",
            field=models.DateTimeField(
                blank=True,
                editable=False,
                null=True,
                verbose_name="email verified at",
            ),
        ),
        migrations.RunPython(create_role_groups, reverse_code=migrations.RunPython.noop),
    ]
