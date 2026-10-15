"""
Management command: seed_ui_states
===================================
Populates the database with demo data covering all visual states needed for
local UI testing (match cards, predictions page, rankings, leagues).

Refuses to run if DEBUG=False.

Usage:
    python manage.py seed_ui_states           # Idempotent — safe to re-run
    python manage.py seed_ui_states --reset   # Tear down and recreate all demo data

Demo data identifiers (safe to purge without touching prod data):
    Competition code:    __DEMO__  (external_id=-999, season='9999')
    Team external_ids:   -1 to -6
    Match external_ids:  -1 to -9
    Users:               username prefix 'demo_'
    League name:         'Demo League'

sync_all_competitions() behaviour with this competition:
    The __DEMO__ competition is is_active=True, so sync_all_competitions() will
    call sync_competition_matches('__DEMO__'), which calls _get_fixtures(-999, '9999').
    The API request returns an HTTP error for this fake external_id.
    _get_fixtures() catches the RequestException, logs it, and returns None.
    sync_competition_matches() then returns early with api_error=True — no Python
    exception raised, no data corruption.
    The live-sync loop also runs for matches with past datetimes (matches -5, -6),
    but each _get_match(-N) call returns None and is skipped via 'continue'.
    Net effect: a few logged API errors, no prod data affected.
"""

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


COMP_CODE = '__DEMO__'
COMP_EXTERNAL_ID = -999
USER_PREFIX = 'demo_'
LEAGUE_NAME = 'Demo League'
MAIN_PASSWORD = 'demo1234'


class Command(BaseCommand):
    help = 'Seed UI visual states for local development. Refuses to run if DEBUG=False.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete all demo data then recreate from scratch.',
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                'Refused: DEBUG=False. This command is for local development only.'
            )

        if options['reset']:
            self._teardown()

        matches = self._seed()
        self._print_summary(matches)

    # ------------------------------------------------------------------
    # Teardown
    # ------------------------------------------------------------------

    def _teardown(self):
        from apps.leagues.models import League
        from apps.matches.models import Competition
        from django.contrib.auth import get_user_model

        User = get_user_model()

        # Leagues first — creator FK would cascade anyway, but being explicit
        # avoids relying on cascade ordering.
        leagues_deleted, _ = League.objects.filter(name=LEAGUE_NAME).delete()
        # Competition cascade: Match → Prediction → UserScore (competition-scoped)
        comps_deleted, _ = Competition.objects.filter(code=COMP_CODE).delete()
        # Users cascade: Prediction, UserScore (global), created leagues
        users_deleted, _ = User.objects.filter(username__startswith=USER_PREFIX).delete()

        self.stdout.write(
            f'  Teardown: {comps_deleted} competition(s), '
            f'{users_deleted} user(s), {leagues_deleted} league(s) deleted'
        )

    # ------------------------------------------------------------------
    # Seed
    # ------------------------------------------------------------------

    def _seed(self):
        from apps.leagues.models import League
        from apps.matches.models import Competition, Match, Team
        from apps.matches.services import _calculate_points_for_match
        from apps.predictions.models import Prediction
        from django.contrib.auth import get_user_model

        User = get_user_model()
        now = timezone.now()

        # --- Competition ---
        # FIXED scoring makes demo points predictable: EXACT=5, GAP=3, WIN=1, MISS=0.
        # unique_together is (external_id, season), so we look up on those two fields.
        comp, _ = Competition.objects.update_or_create(
            external_id=COMP_EXTERNAL_ID,
            season='9999',
            defaults={
                'code': COMP_CODE,
                'name': 'UI Demo',
                'country': 'Demo',
                'scoring_system': 'FIXED',
                'good_gap_pts': 3,
                'is_active': True,
            },
        )

        # --- Teams ---
        # For matches 1-8: prefer real DB teams by slug (logos load from static/img/teams/).
        # Falls back to demo teams with prefixed slugs if sync hasn't run yet (fresh install).
        # Match -9 intentionally tests two edge cases that real teams cannot cover:
        #   team -5: very long name → text overflow / truncation behaviour
        #   team -6: no PNG exists → initials fallback rendering
        logo_teams = [
            (-1, 'Stade Toulousain', 'toulouse',   'ST'),
            (-2, 'Racing 92',        'racing92',   'R92'),
            (-3, 'Stade Rochelais',  'larochelle', 'SRO'),
            (-4, 'ASM Clermont',     'clermont',   'ASM'),
        ]
        teams = {}
        for external_id, name, slug, short_name in logo_teams:
            real = Team.objects.filter(slug=slug, external_id__gt=0).first()
            if real:
                teams[external_id] = real
            else:
                # Fresh install: create demo team with prefixed slug; won't conflict on later sync
                team, _ = Team.objects.update_or_create(
                    external_id=external_id,
                    defaults={'name': name, 'slug': f'demo-{slug}', 'short_name': short_name},
                )
                teams[external_id] = team

        # Match -9 only: always create as demo (no real-world equivalent needed)
        for external_id, name, slug, short_name in [
            (-5, 'Stade Aurillacois Cantal Auvergne Football Club de Rugby', 'demo-long-name-club', 'SAC'),
            (-6, 'Demo No Logo FC', 'demo-no-logo', 'DNL'),
        ]:
            team, _ = Team.objects.update_or_create(
                external_id=external_id,
                defaults={'name': name, 'slug': slug, 'short_name': short_name},
            )
            teams[external_id] = team

        # --- Users ---
        user_specs = [
            {'username': 'demo_main',    'display_name': 'DemoMain'},
            {'username': 'demo_player1', 'display_name': 'Player One'},
            {'username': 'demo_player2', 'display_name': 'Player Two'},
            {'username': 'demo_player3', 'display_name': 'Player Three'},
            {'username': 'demo_player4', 'display_name': 'Player Four'},
            {'username': 'demo_player5', 'display_name': 'Player Five'},
            {'username': 'demo_player6', 'display_name': 'Player Six'},
            # Long display_name — tests text overflow in ranking table
            {'username': 'demo_player7', 'display_name': 'Grand Joueur de Pronostics du Monde Entier'},
        ]
        users = {}
        for spec in user_specs:
            user, created = User.objects.get_or_create(
                username=spec['username'],
                defaults={
                    'email': f"{spec['username']}@demo.local",
                    'display_name': spec['display_name'],
                    'is_active': True,
                },
            )
            if created:
                user.set_password(MAIN_PASSWORD)
                user.save(update_fields=['password'])
            users[spec['username']] = user

        main = users['demo_main']

        # --- Matches ---
        # Datetimes are relative to now() so all states remain valid on every re-run.
        # For FINISHED match 7: home wins 24-17 (gap=7, good_gap_pts=3).
        #   EXACT  : predicted 24-17
        #   GAP    : predicted 22-17 → pred_gap=5, |5-7|=2 ≤ 3
        #   WIN    : predicted 35-10 → pred_gap=25, |25-7|=18 > 3, correct winner
        #   MISS   : predicted 10-28 → wrong winner
        match_defs = [
            {
                'external_id': -1,
                'home': -1, 'away': -2,
                'dt': now + timedelta(days=3),
                'status': Match.STATUS_SCHEDULED,
                'cote_home': 18, 'cote_draw': 60, 'cote_away': 38,
                'round': 'D1',
                'label': 'Open — has odds, no prediction',
            },
            {
                'external_id': -2,
                'home': -3, 'away': -4,
                'dt': now + timedelta(days=5),
                'status': Match.STATUS_SCHEDULED,
                'cote_home': 22, 'cote_draw': 58, 'cote_away': 32,
                'round': 'D2',
                'label': 'Open — has odds, prediction saved',
            },
            {
                'external_id': -3,
                'home': -1, 'away': -3,
                'dt': now + timedelta(hours=12),
                'status': Match.STATUS_SCHEDULED,
                'cote_home': 16, 'cote_draw': 65, 'cote_away': 42,
                'round': 'D3',
                'label': 'Closes soon (closes_soon=True, kickoff in 12h)',
            },
            {
                'external_id': -4,
                'home': -2, 'away': -4,
                'dt': now + timedelta(days=7),
                'status': Match.STATUS_SCHEDULED,
                'cote_home': None, 'cote_draw': None, 'cote_away': None,
                'round': 'D4',
                'label': 'No odds (has_odds=False)',
            },
            {
                'external_id': -5,
                'home': -1, 'away': -4,
                # Past kickoff → is_locked=True, status still SCHEDULED
                'dt': now - timedelta(minutes=30),
                'status': Match.STATUS_SCHEDULED,
                'cote_home': 20, 'cote_draw': 58, 'cote_away': 28,
                'round': 'D5',
                'label': 'Locked (is_locked=True, status=SCHEDULED, kickoff 30min ago)',
            },
            {
                'external_id': -6,
                'home': -3, 'away': -2,
                'dt': now - timedelta(minutes=45),
                'status': Match.STATUS_IN_PLAY,
                'cote_home': 15, 'cote_draw': 70, 'cote_away': 45,
                'round': 'D6',
                'label': 'IN_PLAY — with prediction',
            },
            {
                'external_id': -7,
                'home': -1, 'away': -2,
                'dt': now - timedelta(days=3),
                'status': Match.STATUS_FINISHED,
                'home_score': 24, 'away_score': 17,
                'cote_home': 16, 'cote_draw': 62, 'cote_away': 38,
                'round': 'D7',
                'label': 'FINISHED — EXACT / GAP / WIN / MISS (4 users + 4 extra)',
            },
            {
                'external_id': -8,
                'home': -3, 'away': -4,
                'dt': now - timedelta(days=5),
                'status': Match.STATUS_CANCELLED,
                'cote_home': 20, 'cote_draw': 58, 'cote_away': 28,
                'round': 'D8',
                'label': 'CANCELLED — with prediction (result_type=CANCELLED, 0 pts)',
            },
            {
                'external_id': -9,
                'home': -5, 'away': -6,
                'dt': now + timedelta(days=10),
                'status': Match.STATUS_SCHEDULED,
                'cote_home': 18, 'cote_draw': 65, 'cote_away': 30,
                'round': 'D9',
                'label': 'Long team name + no logo (fallback initials for both teams)',
            },
        ]

        m = {}
        created_matches = []
        for d in match_defs:
            match, _ = Match.objects.update_or_create(
                external_id=d['external_id'],
                defaults={
                    'competition': comp,
                    'home_team': teams[d['home']],
                    'away_team': teams[d['away']],
                    'datetime': d['dt'],
                    'status': d['status'],
                    'cote_home': d.get('cote_home'),
                    'cote_draw': d.get('cote_draw'),
                    'cote_away': d.get('cote_away'),
                    'round': d['round'],
                    'home_score': d.get('home_score'),
                    'away_score': d.get('away_score'),
                },
            )
            m[d['external_id']] = match
            created_matches.append((match, d['label']))

        # --- Predictions ---

        # Match 2: main has a saved prediction (open match, visible in form)
        Prediction.objects.get_or_create(
            user=main, match=m[-2],
            defaults={'predicted_home_score': 28, 'predicted_away_score': 15},
        )

        # Match 5: main had predicted before kickoff; match is now locked
        Prediction.objects.get_or_create(
            user=main, match=m[-5],
            defaults={'predicted_home_score': 21, 'predicted_away_score': 17},
        )

        # Match 6: IN_PLAY — main predicted before kickoff
        Prediction.objects.get_or_create(
            user=main, match=m[-6],
            defaults={'predicted_home_score': 30, 'predicted_away_score': 10},
        )

        # Match 7: FINISHED — 8 predictions covering all result types + populated ranking
        finished_preds = [
            (main,                   24, 17),  # EXACT (exact score)
            (users['demo_player1'],  22, 17),  # GAP   (pred_gap=5, |5-7|=2 ≤ 3)
            (users['demo_player2'],  35, 10),  # WIN   (pred_gap=25, correct winner)
            (users['demo_player3'],  10, 28),  # MISS  (wrong winner)
            (users['demo_player4'],  24, 17),  # EXACT
            (users['demo_player5'],  25, 19),  # GAP   (pred_gap=6, |6-7|=1 ≤ 3)
            (users['demo_player6'],  32, 12),  # WIN   (pred_gap=20)
            (users['demo_player7'],  14, 30),  # MISS  (wrong winner)
        ]
        for user, h, a in finished_preds:
            Prediction.objects.get_or_create(
                user=user, match=m[-7],
                defaults={'predicted_home_score': h, 'predicted_away_score': a},
            )

        # Match 8: CANCELLED — main had a prediction
        Prediction.objects.get_or_create(
            user=main, match=m[-8],
            defaults={'predicted_home_score': 21, 'predicted_away_score': 17},
        )

        # --- Score calculation (via service, never manually) ---
        # _calculate_points_for_match() sets points_earned + result_type on each
        # Prediction, then calls refresh_user_scores_for_match() to update the
        # UserScore cache for the global and per-competition scopes.
        _calculate_points_for_match(m[-7])  # FINISHED → EXACT/GAP/WIN/MISS + UserScore
        _calculate_points_for_match(m[-8])  # CANCELLED → 0 pts, result_type=CANCELLED

        # --- League ---
        league, _ = League.objects.get_or_create(
            name=LEAGUE_NAME,
            defaults={'creator': main},
        )
        league.competitions.add(comp)
        league.members.add(
            main,
            users['demo_player1'],
            users['demo_player2'],
            users['demo_player3'],
        )

        return created_matches

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def _print_summary(self, matches):
        self.stdout.write('\n' + self.style.SUCCESS('=== Demo data seeded ===') + '\n')
        self.stdout.write(f'  Login:         demo_main  /  {MAIN_PASSWORD}')
        self.stdout.write(f'  All demo users share the same password: {MAIN_PASSWORD}')
        self.stdout.write(f'  Usernames:     demo_main, demo_player1 … demo_player7\n')

        self.stdout.write('  Matches:')
        for match, label in matches:
            self.stdout.write(
                f'    [{match.external_id:3d}]  {label}\n'
                f'           /admin/matches/match/{match.pk}/change/'
            )

        self.stdout.write(
            f'\n  League:  "{LEAGUE_NAME}"  (demo_main + player1/2/3)'
            f'\n\n  To wipe and recreate:'
            f'\n    python manage.py seed_ui_states --reset\n'
        )
