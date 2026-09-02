from datetime import date

from django.core.management.base import BaseCommand

from apps.matches.models import Competition


class Command(BaseCommand):
    help = "Set is_active=False for competitions whose end_date has passed."

    def handle(self, *args, **options):
        expired = Competition.objects.filter(is_active=True, end_date__lt=date.today())
        count = expired.count()
        expired.update(is_active=False)
        self.stdout.write(f"Deactivated {count} competition(s).")
