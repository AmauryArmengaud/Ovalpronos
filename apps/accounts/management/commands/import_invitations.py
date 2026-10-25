"""
Commande Django : python manage.py import_invitations
=====================================================
Crée une invitation de réinscription préremplie par ancien joueur, à partir
de l'export de contacts de la campagne (colonnes EMAIL, PSEUDO, COHORTE).

Écrit un CSV EMAIL,TOKEN à réimporter dans Brevo (attribut TOKEN). Le lien
envoyé est alors : <site>/accounts/register/?invite={{ contact.TOKEN }}

Les emails déjà inscrits sont ignorés. Relançable sans risque : une invitation
existante garde son token.

Usage :
    python manage.py import_invitations contacts.csv --output tokens_brevo.csv
"""

import csv

from django.core.management.base import BaseCommand

from apps.accounts.models import CustomUser, Invitation


class Command(BaseCommand):
    help = "Crée les invitations de réinscription et exporte les tokens pour Brevo"

    def add_arguments(self, parser):
        parser.add_argument('contacts', help="CSV avec les colonnes EMAIL, PSEUDO, COHORTE")
        parser.add_argument('--output', required=True, help="CSV EMAIL,TOKEN à importer dans Brevo")

    def handle(self, *args, **options):
        registered = {e.lower() for e in CustomUser.objects.values_list('email', flat=True)}
        created = skipped = 0
        rows = []

        with open(options['contacts'], newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                email = row['EMAIL'].strip().lower()
                if email in registered:
                    skipped += 1
                    continue
                invitation, is_new = Invitation.objects.get_or_create(
                    email=email,
                    defaults={
                        'pseudo': row.get('PSEUDO', '').strip()[:50],
                        'cohort': row.get('COHORTE', '').strip()[:20],
                    },
                )
                created += is_new
                if invitation.used_at is None:
                    rows.append((email, invitation.token))

        with open(options['output'], 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['EMAIL', 'TOKEN'])
            writer.writerows(rows)

        self.stdout.write(self.style.SUCCESS(
            f"{created} invitation(s) créée(s), {skipped} email(s) déjà inscrit(s), "
            f"{len(rows)} token(s) exporté(s) vers {options['output']}"
        ))
