from django.core.management.base import BaseCommand
from apps.predictions.tasks import send_deadline_reminders


class Command(BaseCommand):
    help = 'Send prediction deadline reminders to users with 0 predictions on the upcoming round (22–26h window).'

    def handle(self, *args, **options):
        sent = send_deadline_reminders()
        self.stdout.write(self.style.SUCCESS(f'{sent} reminder(s) sent.'))
