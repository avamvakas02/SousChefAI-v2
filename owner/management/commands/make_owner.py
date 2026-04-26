from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Grant or remove in-site owner access for an existing user."

    def add_arguments(self, parser):
        parser.add_argument("username", help="Username of the account to update.")
        parser.add_argument(
            "--remove",
            action="store_true",
            help="Remove owner access instead of granting it.",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        username = options["username"]
        try:
            user = User.objects.get(username__iexact=username)
        except User.DoesNotExist as exc:
            raise CommandError(f"User {username!r} does not exist.") from exc

        user.is_staff = not options["remove"]
        user.save(update_fields=["is_staff"])

        if user.is_staff:
            self.stdout.write(self.style.SUCCESS(f"{user.username} is now an owner."))
        else:
            self.stdout.write(
                self.style.SUCCESS(f"{user.username} no longer has owner access.")
            )
