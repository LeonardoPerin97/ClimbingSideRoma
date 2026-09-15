from typing import Any

from django.db import migrations, models


def copy_route_setters_to_text(apps: Any, schema_editor: Any) -> None:
    del schema_editor
    ClimbingRoute = apps.get_model("climbs", "ClimbingRoute")
    for climbing_route in ClimbingRoute.objects.all().iterator():
        setter_names = climbing_route.route_setters.order_by("username").values_list(
            "username",
            flat=True,
        )
        climbing_route.route_setter_text = ", ".join(setter_names)
        climbing_route.save(update_fields=("route_setter_text",))


class Migration(migrations.Migration):
    dependencies = [
        ("climbs", "0005_climbingroute_notes"),
    ]

    operations = [
        migrations.AddField(
            model_name="climbingroute",
            name="route_setter_text",
            field=models.TextField(blank=True, default="", verbose_name="route setters"),
        ),
        migrations.RunPython(copy_route_setters_to_text, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="climbingroute",
            name="route_setters",
        ),
        migrations.RenameField(
            model_name="climbingroute",
            old_name="route_setter_text",
            new_name="route_setters",
        ),
        migrations.AlterField(
            model_name="climbingroute",
            name="route_setters",
            field=models.TextField(blank=True, verbose_name="route setters"),
        ),
    ]
