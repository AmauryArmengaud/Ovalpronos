from django.core.management.base import BaseCommand
from apps.predictions.tasks import send_results_summary


class Command(BaseCommand):
    help = 'Send round results summary emails. Auto-detects recently completed rounds, or target a specific one.'

    def add_arguments(self, parser):
        parser.add_argument('--competition-id', type=int, default=None, dest='competition_id',
                            help='Competition DB ID (use with --round)')
        parser.add_argument('--round', type=str, default=None, dest='round_label',
                            help='Round label, e.g. "26" (use with --competition-id)')

    def handle(self, *args, **options):
        sent = send_results_summary(
            competition_id=options['competition_id'],
            round_label=options['round_label'],
        )
        self.stdout.write(self.style.SUCCESS(f'{sent} summary email(s) sent.'))
