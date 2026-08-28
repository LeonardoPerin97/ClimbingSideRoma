from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.roles import Role, assign_role
from apps.climbs.grades import encode_perceived_grade
from apps.climbs.models import Ascent, ClimbingRoute, Wall

DEMO_PREFIX = "[DEMO]"
DEMO_EMAIL_DOMAIN = "example.invalid"


@dataclass
class SeedCounts:
    created: int = 0
    reused: int = 0
    skipped: int = 0

    def add(self, *, created: bool) -> None:
        if created:
            self.created += 1
        else:
            self.reused += 1


class Command(BaseCommand):
    help = "Create deterministic, non-sensitive demonstration data without duplicates."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate the seed operation and roll back every database change.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        del args
        counts = SeedCounts()
        with transaction.atomic():
            users = self._seed_users(counts)
            walls = self._seed_walls(counts)
            routes = self._seed_routes(counts, walls, users.get("demo-setter"))
            self._seed_ascents(counts, users, routes)
            if options["dry_run"]:
                transaction.set_rollback(True)

        mode = "dry-run" if options["dry_run"] else "applied"
        self.stdout.write(
            self.style.SUCCESS(
                f"Demo seed {mode}: created={counts.created}, "
                f"reused={counts.reused}, skipped={counts.skipped}."
            )
        )

    def _seed_users(self, counts: SeedCounts) -> dict[str, User]:
        definitions = (
            ("demo-setter", Role.ROUTE_SETTER),
            ("demo-alex", Role.USER),
            ("demo-marta", Role.USER),
        )
        users: dict[str, User] = {}
        for username, role in definitions:
            email = f"{username}@{DEMO_EMAIL_DOMAIN}"
            existing = User.objects.filter(username__iexact=username).first()
            if existing and existing.email.casefold() != email:
                counts.skipped += 1
                continue
            if existing:
                user = existing
                created = False
            else:
                user = User(username=username, email=email)
                created = True
            user.email = email
            user.is_active = True
            user.email_verified_at = user.email_verified_at or timezone.now()
            user.preferred_language = User.Language.ITALIAN
            user.set_unusable_password()
            user.full_clean()
            user.save()
            assign_role(user, role)
            counts.add(created=created)
            users[username] = user
        return users

    def _seed_walls(self, counts: SeedCounts) -> dict[str, Wall]:
        walls: dict[str, Wall] = {}
        for name in (f"{DEMO_PREFIX} North", f"{DEMO_PREFIX} Cave", f"{DEMO_PREFIX} Slab"):
            wall = Wall.objects.filter(name__iexact=name).first()
            created = wall is None
            wall = wall or Wall(name=name)
            wall.is_archived = False
            wall.full_clean()
            wall.save()
            counts.add(created=created)
            walls[name] = wall
        return walls

    def _seed_routes(
        self,
        counts: SeedCounts,
        walls: dict[str, Wall],
        route_setter: User | None,
    ) -> dict[str, ClimbingRoute]:
        definitions = (
            ("Morning Sun", "North", ClimbingRoute.Discipline.ROUTE, "5c", False, True),
            ("Green Wave", "North", ClimbingRoute.Discipline.ROUTE, "6a+", False, True),
            ("First Flight", "North", ClimbingRoute.Discipline.ROUTE, "6c", False, False),
            ("Hidden Line", "Cave", ClimbingRoute.Discipline.ROUTE, "", True, True),
            ("Pocket Rocket", "Cave", ClimbingRoute.Discipline.BOULDER, "6b", False, True),
            ("Moon Step", "Cave", ClimbingRoute.Discipline.BOULDER, "7a", False, True),
            ("Quiet Feet", "Slab", ClimbingRoute.Discipline.BOULDER, "5b", False, False),
            ("Balance Point", "Slab", ClimbingRoute.Discipline.BOULDER, "6a", False, True),
        )
        routes: dict[str, ClimbingRoute] = {}
        for short_name, wall_name, discipline, grade, is_project, assign_setter in definitions:
            name = f"{DEMO_PREFIX} {short_name}"
            climbing_route = ClimbingRoute.objects.filter(name__iexact=name).first()
            created = climbing_route is None
            climbing_route = climbing_route or ClimbingRoute(name=name)
            climbing_route.wall = walls[f"{DEMO_PREFIX} {wall_name}"]
            climbing_route.discipline = discipline
            climbing_route.official_grade = grade
            climbing_route.is_project = is_project
            climbing_route.is_archived = False
            climbing_route.full_clean()
            climbing_route.save()
            if assign_setter and route_setter:
                climbing_route.route_setters.set((route_setter,))
            else:
                climbing_route.route_setters.clear()
            counts.add(created=created)
            routes[short_name] = climbing_route
        return routes

    def _seed_ascents(
        self,
        counts: SeedCounts,
        users: dict[str, User],
        routes: dict[str, ClimbingRoute],
    ) -> None:
        definitions = (
            ("demo-alex", "Morning Sun", 70, 4, "5c", 2, Ascent.AttemptType.ONSIGHT, None),
            ("demo-alex", "Green Wave", 45, 5, "6a+", 4, Ascent.AttemptType.FLASH, None),
            ("demo-alex", "Pocket Rocket", 18, 4, "6b", 3, Ascent.AttemptType.COUNT, 3),
            ("demo-alex", "Balance Point", 4, 5, "6a", 1, Ascent.AttemptType.ONSIGHT, None),
            ("demo-marta", "Quiet Feet", 90, 4, "5b", 0, Ascent.AttemptType.FLASH, None),
            ("demo-marta", "Morning Sun", 62, 5, "5c", 5, Ascent.AttemptType.ONSIGHT, None),
            ("demo-marta", "Green Wave", 30, 4, "6a", 8, Ascent.AttemptType.COUNT, 4),
            ("demo-marta", "Moon Step", 8, 5, "7a", 2, Ascent.AttemptType.COUNT, 6),
        )
        today = timezone.localdate()
        for username, route_name, days_ago, rating, grade, decimal, attempt, number in definitions:
            user = users.get(username)
            climbing_route = routes.get(route_name)
            if user is None or climbing_route is None:
                counts.skipped += 1
                continue
            ascent, created = Ascent.objects.update_or_create(
                user=user,
                climbing_route=climbing_route,
                defaults={
                    "date": today - timedelta(days=days_ago),
                    "rating": rating,
                    "proposed_grade": encode_perceived_grade(grade, decimal),
                    "attempt_type": attempt,
                    "attempt_count": number,
                },
            )
            ascent.full_clean()
            ascent.save()
            counts.add(created=created)
