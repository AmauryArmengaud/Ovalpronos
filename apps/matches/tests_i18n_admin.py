"""
French output of the strings moved into i18n by the conventions PR.

Each msgid must render exactly the text that was hardcoded before, so French
users see no change. Run: python manage.py test apps.matches.tests_i18n_admin
"""
from django.test import SimpleTestCase
from django.utils import translation
from django.utils.translation import gettext, pgettext

# (context, msgid, placeholders, French text displayed before the change)
EXPECTED = [
    (None, "Status (default: upcoming)", None, "Statut (défaut : à venir)"),
    (None, "All matches", None, "Tous les matchs"),
    (None, "Upcoming (SCHEDULED)", None, "À venir (SCHEDULED)"),
    (None, "Finished (FINISHED)", None, "Terminés (FINISHED)"),
    (None, "No odds", None, "Sans cotes"),
    (None, "%(name)s: %(created)s created, %(updated)s updated.",
     {'name': 'Top 14', 'created': 2, 'updated': 5}, "Top 14 : 2 créés, 5 mis à jour."),
    (None, "%(name)s: error, %(error)s", {'name': 'Top 14', 'error': 'timeout'}, "Top 14 : erreur — timeout"),
    (None, "Matches", None, "Matchs"),
    (None, "Sync", None, "Sync"),
    (None, "Sync matches from the API", None, "Synchroniser les matchs depuis l'API"),
    (None, "Recalculate points (finished matches)", None, "Recalculer les points (matchs terminés)"),
    (None, "Recalculation done for %(count)s match(es).", {'count': 3}, "Recalcul terminé pour 3 match(s)."),
    (None, "Fans", None, "Fans"),
    (None, "Upcoming", None, "À venir"),
    (None, "In play", None, "En cours"),
    (None, "Finished", None, "Terminé"),
    (None, "Postponed", None, "Reporté"),
    (None, "Cancelled", None, "Annulé"),
    (None, "Status", None, "Statut"),
    (None, "Score", None, "Score"),
    ("admin column", "Odds", None, "Cotes"),
    (None, "Predictions", None, "Pronos"),
    (None, "Recalculate points", None, "Recalculer les points"),
    (None, "Points recalculated for %(count)s finished match(es).", {'count': 3},
     "Points recalculés pour 3 match(s) terminé(s)."),
    (None, "Refresh the UserScore cache", None, "Rafraîchir le cache UserScore"),
    (None, "UserScore cache refreshed for %(count)s match(es).", {'count': 3},
     "Cache UserScore rafraîchi pour 3 match(s)."),
    (None, "Hide these matches", None, "Masquer ces matchs"),
    (None, "Show these matches", None, "Afficher ces matchs"),
    (None, "Sync done for %(name)s: %(created)s created, %(updated)s updated.",
     {'name': 'Top 14', 'created': 2, 'updated': 5}, "Sync terminée pour Top 14 : 2 créés, 5 mis à jour."),
    (None, "Activate selected accounts", None, "Activer les comptes sélectionnés"),
    (None, "Deactivate selected accounts", None, "Désactiver les comptes sélectionnés"),
    ("admin column", "Members", None, "Members"),
    (None, "Regenerate invite code", None, "Régénérer le code d'invitation"),
    (None, "Code regenerated for %(count)s league(s).", {'count': 3}, "Code régénéré pour 3 ligue(s)."),
    (None, "Exact", None, "Exact"),
    (None, "Good gap", None, "Bon écart"),
    (None, "Winner", None, "Vainqueur"),
    (None, "Missed", None, "Raté"),
    (None, "Match", None, "Match"),
    (None, "Prediction", None, "Pronostic"),
    (None, "Result", None, "Résultat"),
    (None, "Points recalculated for %(count)s match(es).", {'count': 3}, "Points recalculés pour 3 match(s)."),
    (None, "Scope", None, "Portée"),
    ("ranking scope", "Global", None, "Global"),
    (None, "Competition: %(name)s", {'name': 'Top 14'}, "Compétition : Top 14"),
    (None, "League: %(name)s", {'name': 'Les Potes'}, "Ligue : Les Potes"),
    (None, "Cache refreshed for %(count)s entry(ies).", {'count': 3}, "Cache rafraîchi pour 3 entrée(s)."),
    (None, "Active players", None, "Joueurs actifs"),
    (None, "Matches this week", None, "Matchs cette semaine"),
    (None, "Matches without odds", None, "Matchs sans cotes"),
    (None, "Unscored predictions", None, "Pronos non calculés"),
    (None, "Dashboard", None, "Dashboard"),
    (None, "Admin", None, "Admin"),
    (None, "Oval'Pronos mascot", None, "Mascotte Oval'Pronos"),
    (None, "pts", None, "pts"),
    (None, "pt", None, "pt"),
]


class FrenchTextUnchangedTest(SimpleTestCase):
    def test_french_translation_equals_previous_text(self):
        with translation.override('fr'):
            for context, msgid, params, expected in EXPECTED:
                with self.subTest(msgid=msgid, context=context):
                    text = pgettext(context, msgid) if context else gettext(msgid)
                    if params:
                        text = text % params
                    self.assertEqual(text, expected)
