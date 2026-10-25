"""
Commande Django : python manage.py sync_brevo_contacts
======================================================
Pousse vers Brevo l'état des anciens joueurs 2023 pour la campagne de relance :
  - INSCRIT_V2       : true dès qu'un compte existe avec l'email de l'invitation
  - LIGUE_NOM        : nom de sa ligue la plus peuplée (vide sans ligue)
  - NB_MEMBRES_LIGUE : nombre de membres de cette ligue (0 sans ligue)

Les segments Brevo « Non réinscrits » / « Réinscrits » reposent sur INSCRIT_V2.
Lancée chaque nuit par le cron du VPS, et à la main avant chaque envoi.
Les contacts absents de Brevo sont ignorés.

Usage :
    python manage.py sync_brevo_contacts
"""

from urllib.parse import quote

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count
from django.db.models.functions import Lower

from apps.accounts.models import CustomUser, Invitation
from apps.leagues.models import League

BREVO_CONTACT_URL = 'https://api.brevo.com/v3/contacts/{}'


def contact_attributes(user):
    # Counting on user.leagues would reuse the membership join and always return 1
    league = (
        League.objects.filter(pk__in=user.leagues.values('pk'))
        .annotate(nb_members=Count('members'))
        .order_by('-nb_members', 'created_at')
        .first()
    )
    return {
        'INSCRIT_V2': True,
        'LIGUE_NOM': league.name if league else '',
        'NB_MEMBRES_LIGUE': league.nb_members if league else 0,
    }


class Command(BaseCommand):
    help = "Synchronise INSCRIT_V2, LIGUE_NOM et NB_MEMBRES_LIGUE des joueurs 2023 vers Brevo"

    def handle(self, *args, **options):
        api_key = settings.ANYMAIL.get('BREVO_API_KEY')
        if not api_key:
            raise CommandError("BREVO_API_KEY absente : rien n'est envoyé à Brevo")

        # Also catches 2023 players who signed up without their invitation link
        users = CustomUser.objects.annotate(email_lower=Lower('email')).filter(
            email_lower__in=Invitation.objects.values('email')
        )

        updated = not_in_brevo = failed = 0
        for user in users:
            try:
                response = requests.put(
                    BREVO_CONTACT_URL.format(quote(user.email.lower())),
                    params={'identifierType': 'email_id'},
                    json={'attributes': contact_attributes(user)},
                    headers={'api-key': api_key},
                    timeout=15,
                )
                if response.status_code == 404:
                    not_in_brevo += 1
                    continue
                response.raise_for_status()
                updated += 1
            except requests.RequestException as e:
                failed += 1
                self.stderr.write(f"{user.email} : {e}")

        summary = f"{updated} contact(s) mis à jour, {not_in_brevo} absent(s) de Brevo, {failed} échec(s)"
        if failed:
            raise CommandError(summary)
        self.stdout.write(self.style.SUCCESS(summary))
