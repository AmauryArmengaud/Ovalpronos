"""
Commande Django : python manage.py sync_matches
================================================
Lance la synchronisation des matchs pour toutes les compétitions actives.
Cette commande est appelée automatiquement par le cron (toutes les 2h).

Usage :
    python manage.py sync_matches                  # Toutes les compétitions
    python manage.py sync_matches --comp TOP14     # Une seule compétition
"""

from django.core.management.base import BaseCommand
from django.conf import settings
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

        if comp_code:
            competitions = [comp_code]
        else:
            competitions = list(settings.RUGBY_COMPETITIONS.keys())

        total_created = 0
        total_updated = 0

        for code in competitions:
            self.stdout.write(f"  → Synchronisation {code}...", ending='')
            created, updated = sync_competition_matches(code)
            total_created += created
            total_updated += updated
            self.stdout.write(
                self.style.SUCCESS(f" {created} créés, {updated} mis à jour")
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✓ Sync terminée : {total_created} matchs créés, {total_updated} mis à jour"
            )
        )
