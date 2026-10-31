"""
Django command: python manage.py sync_matches
==============================================
Syncs the matches of every active competition.
Run automatically by the VPS cron (daily, 07:00 UTC).

Usage:
    python manage.py sync_matches                  # All competitions
    python manage.py sync_matches --comp TOP14     # A single competition
"""

from django.core.management.base import BaseCommand
from apps.matches.services import sync_competition_matches


class Command(BaseCommand):
    help = 'Synchronise les matchs et résultats depuis api-sports.io / Rugby API'

    def add_arguments(self, parser):
        parser.add_argument(
            '--comp',
            type=str,
            help='Code de la compétition à synchroniser (ex: TOP14, CHAMPIONS_CUP)',
            default=None,
        )

    def handle(self, *args, **options):
        comp_code = options.get('comp')

        from apps.matches.models import Competition
        # Competition rows, not codes: a code is shared by every season of a competition
        competitions = Competition.objects.filter(is_active=True)
        if comp_code:
            competitions = competitions.filter(code=comp_code)
            if not competitions:
                self.stderr.write(self.style.ERROR(f"Aucune compétition active pour le code {comp_code}"))
                return

        total_created = 0
        total_updated = 0

        for comp in competitions:
            self.stdout.write(f"  → Synchronisation {comp.code} ({comp.season})...", ending='')
            r = sync_competition_matches(comp)
            total_created += r['created']
            total_updated += r['updated']
            self.stdout.write(
                self.style.SUCCESS(f" {r['created']} créés, {r['updated']} mis à jour")
            )
            for change in r['changes']:
                self.stdout.write(f"     {change}")

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✓ Sync terminée : {total_created} matchs créés, {total_updated} mis à jour"
            )
        )
