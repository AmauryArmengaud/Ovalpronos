"""
One-shot command to populate Team.logo from existing static PNG files.

Usage:
    python manage.py migrate_team_logos
    python manage.py migrate_team_logos --dry-run
"""

from pathlib import Path
from django.core.management.base import BaseCommand
from django.core.files import File
from django.conf import settings


class Command(BaseCommand):
    help = 'Copy static team logos into Team.logo (media upload field)'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        from apps.matches.models import Team

        dry_run = options['dry_run']
        static_logos = Path(settings.BASE_DIR) / 'static' / 'img' / 'teams'

        migrated = 0
        skipped = 0
        missing = 0

        for team in Team.objects.all():
            if team.logo:
                skipped += 1
                continue

            png = static_logos / f'{team.slug}.png'
            if not png.exists():
                self.stdout.write(f'  no file : {team.slug}.png')
                missing += 1
                continue

            if not dry_run:
                with png.open('rb') as f:
                    team.logo.save(f'{team.slug}.png', File(f), save=True)

            self.stdout.write(self.style.SUCCESS(f'  {"[dry] " if dry_run else ""}migrated : {team.slug}'))
            migrated += 1

        self.stdout.write(
            self.style.SUCCESS(f'\nDone — migrated: {migrated}, already set: {skipped}, no file: {missing}')
        )
