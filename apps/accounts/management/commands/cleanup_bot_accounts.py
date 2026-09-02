"""
Commande Django : python manage.py cleanup_bot_accounts
========================================================
Identifie et supprime les comptes suspects créés par des robots.

Critères de détection (tous requis simultanément) :
  - Aucun pronostic soumis
  - Aucune ligue créée ni rejointe
  - Non staff / non superuser

Options :
    --dry-run          Affiche les comptes qui seraient supprimés, sans toucher la base
    --since YYYY-MM-DD Ne considère que les comptes créés après cette date
    --yes              Confirme sans prompt interactif (pour les scripts)

Usage :
    python manage.py cleanup_bot_accounts --dry-run
    python manage.py cleanup_bot_accounts --since 2025-01-01 --dry-run
    python manage.py cleanup_bot_accounts --yes
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils.timezone import make_aware
from datetime import datetime

from apps.accounts.models import CustomUser


class Command(BaseCommand):
    help = "Supprime les comptes suspects sans aucune activité (bots d'inscription)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help="Affiche les comptes concernés sans les supprimer",
        )
        parser.add_argument(
            '--since',
            metavar='YYYY-MM-DD',
            help="Ne considère que les comptes créés à partir de cette date",
        )
        parser.add_argument(
            '--yes',
            action='store_true',
            help="Confirme la suppression sans prompt interactif",
        )

    def handle(self, *args, **options):
        qs = CustomUser.objects.filter(
            is_staff=False,
            is_superuser=False,
        ).filter(
            predictions__isnull=True,  # aucun pronostic
        ).filter(
            leagues__isnull=True,      # aucune ligue (membre ou créateur)
        ).filter(
            created_leagues__isnull=True,
        )

        if options['since']:
            try:
                since_dt = make_aware(datetime.strptime(options['since'], '%Y-%m-%d'))
            except ValueError:
                raise CommandError("Format de date invalide. Utilisez YYYY-MM-DD.")
            qs = qs.filter(date_joined__gte=since_dt)

        qs = qs.order_by('date_joined')
        count = qs.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS("Aucun compte suspect trouvé."))
            return

        self.stdout.write(f"\n{count} compte(s) suspect(s) trouvé(s) :\n")
        self.stdout.write(f"{'ID':>6}  {'Username':<30}  {'Email':<35}  {'Créé le'}")
        self.stdout.write("-" * 90)
        for user in qs:
            self.stdout.write(
                f"{user.pk:>6}  {user.username:<30}  {user.email:<35}  "
                f"{user.date_joined.strftime('%Y-%m-%d %H:%M')}"
            )

        if options['dry_run']:
            self.stdout.write(self.style.WARNING(f"\n[dry-run] Aucune suppression effectuée."))
            return

        if not options['yes']:
            self.stdout.write("")
            confirm = input(f"Supprimer ces {count} compte(s) ? [oui/N] ").strip().lower()
            if confirm != 'oui':
                self.stdout.write(self.style.WARNING("Annulé."))
                return

        deleted, _ = qs.delete()
        self.stdout.write(self.style.SUCCESS(f"\n{deleted} compte(s) supprimé(s)."))
