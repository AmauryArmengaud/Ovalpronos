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
    Match external_ids:  -1 to -10
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
ENDED_COMP_CODE = '__DEMO_ENDED__'
ENDED_COMP_EXTERNAL_ID = -998
# Extra competitions for chip-overflow visual testing (no matches needed)
EXTRA_COMP_DEFS = [
    ('__DEMO_C2__', -997, 'Champions Cup'),
    ('__DEMO_C3__', -996, '6 Nations'),
    ('__DEMO_C4__', -995, 'Top 14'),
    ('__DEMO_C5__', -994, 'URC'),
    ('__DEMO_C6__', -993, 'Premiership'),
]
USER_PREFIX = 'demo_'
LEAGUE_NAME = 'Demo League'
MEMBER_LEAGUE_NAME = 'Demo Potes'
LONG_LEAGUE_NAME = 'Les Pronostiqueurs du Grand Stade du Midi-Pyrénées'
ENDED_LEAGUE_NAME = 'Demo Saison Passée'
THREE_COMP_LEAGUE_NAME = 'Demo 3 Comps'
SIX_COMP_LEAGUE_NAME = 'Demo 6 Comps'
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
        leagues_deleted, _ = League.objects.filter(name__in=[
            LEAGUE_NAME, 'Demo Liga', MEMBER_LEAGUE_NAME, LONG_LEAGUE_NAME,
            ENDED_LEAGUE_NAME, THREE_COMP_LEAGUE_NAME, SIX_COMP_LEAGUE_NAME,
        ]).delete()
        # Competition cascade: Match → Prediction → UserScore (competition-scoped)
        extra_codes = [c[0] for c in EXTRA_COMP_DEFS]
        comps_deleted, _ = Competition.objects.filter(
            code__in=[COMP_CODE, ENDED_COMP_CODE, *extra_codes]
        ).delete()
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
        # COTES scoring with good_gap_pts=10 produces realistic 4-digit totals.
        # unique_together is (external_id, season), so we look up on those two fields.
        comp, _ = Competition.objects.update_or_create(
            external_id=COMP_EXTERNAL_ID,
            season='9999',
            defaults={
                'code': COMP_CODE,
                'name': 'UI Demo',
                'country': 'Demo',
                'scoring_system': 'COTES',
                'good_gap_pts': 10,
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
            {'username': 'demo_main',     'display_name': 'DemoMain'},
            {'username': 'demo_player1',  'display_name': 'Player One'},
            {'username': 'demo_player2',  'display_name': 'Player Two'},
            {'username': 'demo_player3',  'display_name': 'Player Three'},
            {'username': 'demo_player4',  'display_name': 'Player Four'},
            {'username': 'demo_player5',  'display_name': 'Player Five'},
            {'username': 'demo_player6',  'display_name': 'Player Six'},
            # Long display_name — tests text overflow / ellipsis in ranking table
            {'username': 'demo_player7',  'display_name': 'Grand Joueur de Pronostics du Monde Entier'},
            # Players 8–19: bulk ranking data (20 players total, demo_main ~rank 15)
            {'username': 'demo_player8',  'display_name': 'Arnaud Dupont'},
            {'username': 'demo_player9',  'display_name': 'Camille Morel'},
            {'username': 'demo_player10', 'display_name': 'Théo Laurent'},
            {'username': 'demo_player11', 'display_name': 'Sophie Blanc'},
            {'username': 'demo_player12', 'display_name': 'Lucas Martin'},
            {'username': 'demo_player13', 'display_name': 'Julie Renard'},
            {'username': 'demo_player14', 'display_name': 'Baptiste Roy'},
            {'username': 'demo_player15', 'display_name': 'Chloé Petit'},
            {'username': 'demo_player16', 'display_name': 'Maxime Girard'},
            {'username': 'demo_player17', 'display_name': 'Inès Bernard'},
            {'username': 'demo_player18', 'display_name': 'Nathan Simon'},
            {'username': 'demo_player19', 'display_name': 'Léa Thomas'},
            # demo_newcomer: no predictions at all — tests 0-pt display in active league leaderboard
            {'username': 'demo_newcomer',  'display_name': 'Nouveau Joueur'},
            # demo_no_pronos: no predictions, no leagues — profile empty-state (both sections)
            {'username': 'demo_no_pronos', 'display_name': 'Sans Pronos'},
            # demo_no_league: has scored predictions, no leagues — profile stats + empty leagues
            {'username': 'demo_no_league', 'display_name': 'Sans Ligue'},
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
                'home_score': 27, 'away_score': 14,
                'round': 'D6',
                'label': 'IN_PLAY — with live score + prediction',
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
            {
                'external_id': -10,
                'home': -1, 'away': -3,
                'dt': now + timedelta(days=12),
                'status': Match.STATUS_SCHEDULED,
                'cote_home': 21, 'cote_draw': 60, 'cote_away': 32,
                'round': 'Final',
                'label': 'Playoff round — non-numeric round display (Final → Finale)',
            },
            # ── Ranking matches (FINISHED, past) ──────────────────────────
            # These build realistic COTES scores (4-digit totals) for 20 players.
            # Actual results and cotes are fixed; predicted scores are assigned
            # per player below to produce the desired EXACT/GAP/WIN/MISS types.
            # M-11: home wins 24-10, gap=14
            {'external_id': -11, 'home': -1, 'away': -2,
             'dt': now - timedelta(days=8),  'status': Match.STATUS_FINISHED,
             'home_score': 24, 'away_score': 10,
             'cote_home': 22, 'cote_draw': 58, 'cote_away': 68, 'round': 'D11',
             'label': 'Ranking — M-11 home win'},
            # M-12: away wins 12-31, gap=-19
            {'external_id': -12, 'home': -3, 'away': -4,
             'dt': now - timedelta(days=15), 'status': Match.STATUS_FINISHED,
             'home_score': 12, 'away_score': 31,
             'cote_home': 18, 'cote_draw': 62, 'cote_away': 72, 'round': 'D12',
             'label': 'Ranking — M-12 away win'},
            # M-13: home wins 28-17, gap=11
            {'external_id': -13, 'home': -1, 'away': -4,
             'dt': now - timedelta(days=22), 'status': Match.STATUS_FINISHED,
             'home_score': 28, 'away_score': 17,
             'cote_home': 18, 'cote_draw': 65, 'cote_away': 82, 'round': 'D13',
             'label': 'Ranking — M-13 home win'},
            # M-14: away wins 11-38, gap=-27
            {'external_id': -14, 'home': -2, 'away': -3,
             'dt': now - timedelta(days=29), 'status': Match.STATUS_FINISHED,
             'home_score': 11, 'away_score': 38,
             'cote_home': 16, 'cote_draw': 68, 'cote_away': 85, 'round': 'D14',
             'label': 'Ranking — M-14 away win'},
            # M-15: home wins 22-15, gap=7
            {'external_id': -15, 'home': -4, 'away': -1,
             'dt': now - timedelta(days=36), 'status': Match.STATUS_FINISHED,
             'home_score': 22, 'away_score': 15,
             'cote_home': 24, 'cote_draw': 60, 'cote_away': 66, 'round': 'D15',
             'label': 'Ranking — M-15 home win'},
            # M-16: away wins 14-38, gap=-24
            {'external_id': -16, 'home': -3, 'away': -2,
             'dt': now - timedelta(days=43), 'status': Match.STATUS_FINISHED,
             'home_score': 14, 'away_score': 38,
             'cote_home': 18, 'cote_draw': 66, 'cote_away': 92, 'round': 'D16',
             'label': 'Ranking — M-16 away win'},
            # M-17: home wins 30-14, gap=16
            {'external_id': -17, 'home': -1, 'away': -4,
             'dt': now - timedelta(days=50), 'status': Match.STATUS_FINISHED,
             'home_score': 30, 'away_score': 14,
             'cote_home': 28, 'cote_draw': 62, 'cote_away': 74, 'round': 'D17',
             'label': 'Ranking — M-17 home win'},
            # M-18: away wins 10-38, gap=-28   (high cote → big pts)
            {'external_id': -18, 'home': -2, 'away': -4,
             'dt': now - timedelta(days=57), 'status': Match.STATUS_FINISHED,
             'home_score': 10, 'away_score': 38,
             'cote_home': 16, 'cote_draw': 66, 'cote_away': 148, 'round': 'D18',
             'label': 'Ranking — M-18 away win (high cote)'},
            # M-19: home wins 35-22, gap=13
            {'external_id': -19, 'home': -3, 'away': -1,
             'dt': now - timedelta(days=64), 'status': Match.STATUS_FINISHED,
             'home_score': 35, 'away_score': 22,
             'cote_home': 38, 'cote_draw': 58, 'cote_away': 68, 'round': 'D19',
             'label': 'Ranking — M-19 home win'},
            # M-20: away wins 15-42, gap=-27   (high cote → big pts)
            {'external_id': -20, 'home': -4, 'away': -2,
             'dt': now - timedelta(days=71), 'status': Match.STATUS_FINISHED,
             'home_score': 15, 'away_score': 42,
             'cote_home': 15, 'cote_draw': 65, 'cote_away': 158, 'round': 'D20',
             'label': 'Ranking — M-20 away win (high cote)'},
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

        # Match 3: main has a prediction (closes soon + prediction — Zone C shows saved + potential)
        Prediction.objects.get_or_create(
            user=main, match=m[-3],
            defaults={'predicted_home_score': 22, 'predicted_away_score': 10},
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

        # ── Ranking match predictions ──────────────────────────────────────
        # Target ranking (global, 20 players):
        #   1=P8, 1=P9 (true tie), 3=P13, 4=P12, 5=P10, 6=P11, 7=P16, 8=P15,
        #   9=P14, 10=P18, 11=P17, 12=P19, 13=P4, 14=P5, 15=demo_main,
        #   16=P1, 17=P2/P6 (true tie), 19=P3/P7 (true tie, P7 = long name)
        #
        # Per-match predicted scores per result type:
        #   M-11 (home 24-10, gap=14, cote_home=22): E→(24,10) G→(18,4) W→(30,0) M→(10,24)
        #   M-12 (away 12-31, gap=-19, cote_away=72): E→(12,31) G→(15,34) W→(10,42) M→(20,14)
        #   M-13 (home 28-17, gap=11, cote_home=18): E→(28,17) G→(22,11) W→(35,10) M→(15,25)
        #   M-14 (away 11-38, gap=-27, cote_away=85): E→(11,38) G→(13,42) W→(10,50) M→(25,15)
        #   M-15 (home 22-15, gap=7, cote_home=24): E→(22,15) G→(20,13) W→(35,15) M→(15,22)
        #   M-16 (away 14-38, gap=-24, cote_away=92): E→(14,38) G→(16,40) W→(10,45) M→(20,14)
        #   M-17 (home 30-14, gap=16, cote_home=28): E→(30,14) G→(25,9) W→(40,10) M→(14,30)
        #   M-18 (away 10-38, gap=-28, cote_away=148): E→(10,38) G→(12,40) W→(10,50) M→(20,15)
        #   M-19 (home 35-22, gap=13, cote_home=38): E→(35,22) G→(30,17) W→(40,10) M→(20,35)
        #   M-20 (away 15-42, gap=-27, cote_away=158): E→(15,42) G→(16,43) W→(10,50) M→(30,20)
        #
        # Each entry: (user_key, match_ext_id, pred_home, pred_away)
        p = users  # alias for brevity
        ranking_preds = [
            # P8: EXACT all 10 ranking matches + M-7 → ~2103 pts (true tie with P9)
            ('demo_player8',  -7,  24, 17),
            ('demo_player8',  -11, 24, 10), ('demo_player8',  -12, 12, 31),
            ('demo_player8',  -13, 28, 17), ('demo_player8',  -14, 11, 38),
            ('demo_player8',  -15, 22, 15), ('demo_player8',  -16, 14, 38),
            ('demo_player8',  -17, 30, 14), ('demo_player8',  -18, 10, 38),
            ('demo_player8',  -19, 35, 22), ('demo_player8',  -20, 15, 42),
            # P9: same as P8 — true tie
            ('demo_player9',  -7,  24, 17),
            ('demo_player9',  -11, 24, 10), ('demo_player9',  -12, 12, 31),
            ('demo_player9',  -13, 28, 17), ('demo_player9',  -14, 11, 38),
            ('demo_player9',  -15, 22, 15), ('demo_player9',  -16, 14, 38),
            ('demo_player9',  -17, 30, 14), ('demo_player9',  -18, 10, 38),
            ('demo_player9',  -19, 35, 22), ('demo_player9',  -20, 15, 42),
            # P10: GAP on M-18, EXACT rest → slightly fewer pts
            ('demo_player10', -7,  24, 17),
            ('demo_player10', -11, 24, 10), ('demo_player10', -12, 12, 31),
            ('demo_player10', -13, 28, 17), ('demo_player10', -14, 11, 38),
            ('demo_player10', -15, 22, 15), ('demo_player10', -16, 14, 38),
            ('demo_player10', -17, 30, 14), ('demo_player10', -18, 12, 40),  # GAP
            ('demo_player10', -19, 35, 22), ('demo_player10', -20, 15, 42),
            # P11: GAP on M-20, EXACT rest
            ('demo_player11', -7,  24, 17),
            ('demo_player11', -11, 24, 10), ('demo_player11', -12, 12, 31),
            ('demo_player11', -13, 28, 17), ('demo_player11', -14, 11, 38),
            ('demo_player11', -15, 22, 15), ('demo_player11', -16, 14, 38),
            ('demo_player11', -17, 30, 14), ('demo_player11', -18, 10, 38),
            ('demo_player11', -19, 35, 22), ('demo_player11', -20, 16, 43),  # GAP
            # P12: GAP on M-14, EXACT rest
            ('demo_player12', -7,  24, 17),
            ('demo_player12', -11, 24, 10), ('demo_player12', -12, 12, 31),
            ('demo_player12', -13, 28, 17), ('demo_player12', -14, 13, 42),  # GAP
            ('demo_player12', -15, 22, 15), ('demo_player12', -16, 14, 38),
            ('demo_player12', -17, 30, 14), ('demo_player12', -18, 10, 38),
            ('demo_player12', -19, 35, 22), ('demo_player12', -20, 15, 42),
            # P13: GAP on M-12, EXACT rest
            ('demo_player13', -7,  24, 17),
            ('demo_player13', -11, 24, 10), ('demo_player13', -12, 15, 34),  # GAP
            ('demo_player13', -13, 28, 17), ('demo_player13', -14, 11, 38),
            ('demo_player13', -15, 22, 15), ('demo_player13', -16, 14, 38),
            ('demo_player13', -17, 30, 14), ('demo_player13', -18, 10, 38),
            ('demo_player13', -19, 35, 22), ('demo_player13', -20, 15, 42),
            # P14: WIN on M-18 + WIN on M-20, EXACT rest
            ('demo_player14', -7,  24, 17),
            ('demo_player14', -11, 24, 10), ('demo_player14', -12, 12, 31),
            ('demo_player14', -13, 28, 17), ('demo_player14', -14, 11, 38),
            ('demo_player14', -15, 22, 15), ('demo_player14', -16, 14, 38),
            ('demo_player14', -17, 30, 14), ('demo_player14', -18, 10, 50),  # WIN
            ('demo_player14', -19, 35, 22), ('demo_player14', -20, 10, 50),  # WIN
            # P15: MISS on M-12, WIN on M-14, EXACT rest
            ('demo_player15', -7,  24, 17),
            ('demo_player15', -11, 24, 10), ('demo_player15', -12, 20, 14),  # MISS
            ('demo_player15', -13, 28, 17), ('demo_player15', -14, 10, 50),  # WIN
            ('demo_player15', -15, 22, 15), ('demo_player15', -16, 14, 38),
            ('demo_player15', -17, 30, 14), ('demo_player15', -18, 10, 38),
            ('demo_player15', -19, 35, 22), ('demo_player15', -20, 15, 42),
            # P16: WIN on M-11 + WIN on M-14, EXACT rest
            ('demo_player16', -7,  24, 17),
            ('demo_player16', -11, 30,  0),  # WIN
            ('demo_player16', -12, 12, 31), ('demo_player16', -13, 28, 17),
            ('demo_player16', -14, 10, 50),  # WIN
            ('demo_player16', -15, 22, 15), ('demo_player16', -16, 14, 38),
            ('demo_player16', -17, 30, 14), ('demo_player16', -18, 10, 38),
            ('demo_player16', -19, 35, 22), ('demo_player16', -20, 15, 42),
            # P17: EXACT on M-7 + EXACT on M-19 only
            ('demo_player17', -7,  24, 17),
            ('demo_player17', -19, 35, 22),
            # P18: WIN on M-7(→correct winner) + GAP on M-16 → ~168 pts total
            # M-7: main wins 24-17 (home), WIN pred: home wins big → (35,10)
            # But wait: M-7 uses cote_home=16. WIN on M-7: correct winner (home), gap doesn't match
            # Predicted 35-10: pred_gap=25, real_gap=7, |25-7|=18 > 10 → WIN ✓ → 16×1=16 pts
            # GAP on M-16 (away wins 14-38, gap=-24, cote_away=92):
            # Predicted (16,40): pred_gap=-24, same gap → GAP ✓ → 92×2=184 pts
            ('demo_player18', -7,  35, 10),  # WIN on M-7 (16 pts)
            ('demo_player18', -16, 16, 40),  # GAP on M-16 (184 pts) → total 200 pts
            # P19: GAP on M-7 + GAP on M-11 + WIN on M-13
            # GAP on M-7: pred (22,17) is already used by p1, use (23,16): gap=7, same gap ✓
            ('demo_player19', -7,  23, 16),  # GAP on M-7 (16×2=32 pts)
            ('demo_player19', -11, 18,  4),  # GAP on M-11 (22×2=44 pts)
            ('demo_player19', -13, 35, 10),  # WIN on M-13 (18×1=18 pts)
            # P4: existing EXACT on M-7 + WIN on M-11 → 48+22=70 pts (rank 13)
            ('demo_player4',  -11, 30,  0),  # WIN on M-11
            # P5: existing GAP on M-7 (32 pts) + WIN on M-11 → 32+22=54 pts (rank 14)
            ('demo_player5',  -11, 38, 10),  # WIN on M-11 (pred_gap=28, |28-14|=14>10)
        ]
        for username, match_ext_id, h, a in ranking_preds:
            Prediction.objects.get_or_create(
                user=users[username],
                match=m[match_ext_id],
                defaults={'predicted_home_score': h, 'predicted_away_score': a},
            )

        # demo_no_league: EXACT on M-7 + WIN on M-11 — enough pts to show a real rank
        # Not added to any league → tests profile stats section with empty leagues section
        Prediction.objects.get_or_create(
            user=users['demo_no_league'], match=m[-7],
            defaults={'predicted_home_score': 24, 'predicted_away_score': 17},  # EXACT
        )
        Prediction.objects.get_or_create(
            user=users['demo_no_league'], match=m[-11],
            defaults={'predicted_home_score': 30, 'predicted_away_score': 0},   # WIN
        )

        # --- Score calculation (via service, never manually) ---
        # _calculate_points_for_match() sets points_earned + result_type on each
        # Prediction, then calls refresh_user_scores_for_match() to update the
        # UserScore cache for the global and per-competition scopes.
        # M-7 is scored first so its COTES points are included in the aggregates
        # when ranking matches (which run after) call refresh_user_scores_for_match.
        _calculate_points_for_match(m[-7])  # FINISHED → EXACT/GAP/WIN/MISS + UserScore
        _calculate_points_for_match(m[-8])  # CANCELLED → 0 pts, result_type=CANCELLED
        for ext_id in range(-11, -21, -1):
            _calculate_points_for_match(m[ext_id])

        # --- Ended competition (is_active=False) — for ENDED_LEAGUE_NAME seed ---
        ended_comp, _ = Competition.objects.update_or_create(
            external_id=ENDED_COMP_EXTERNAL_ID,
            season='9998',
            defaults={
                'code': ENDED_COMP_CODE,
                'name': 'UI Demo Terminé',
                'country': 'Demo',
                'scoring_system': 'COTES',
                'good_gap_pts': 10,
                'is_active': False,
            },
        )

        # --- Extra competitions (no matches) — for chip-overflow visual testing ---
        extra_comps = []
        for code, ext_id, name in EXTRA_COMP_DEFS:
            c, _ = Competition.objects.update_or_create(
                external_id=ext_id,
                season='9999',
                defaults={
                    'code': code,
                    'name': name,
                    'country': 'Demo',
                    'scoring_system': 'COTES',
                    'good_gap_pts': 10,
                    'is_active': True,
                },
            )
            extra_comps.append(c)

        # --- Leagues ---
        # Demo League: 4 members — demo_main is creator and rank 1 (tests creator case)
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

        # Demo Liga: all 20 players — makes everyone eligible for the global leaderboard.
        # demo_main is ~rank 15 here. Also tests the league tab with a full leaderboard.
        liga, _ = League.objects.get_or_create(
            name='Demo Liga',
            defaults={'creator': main},
        )
        liga.competitions.add(comp)
        liga.members.add(*users.values())

        # Demo Potes: demo_player1 is creator, demo_main is a simple member.
        # Tests the "Leave" button (demo_main can leave this one).
        potes, _ = League.objects.get_or_create(
            name=MEMBER_LEAGUE_NAME,
            defaults={'creator': users['demo_player1']},
        )
        potes.competitions.add(comp)
        # demo_newcomer has no predictions → visible at 0 pt in active league leaderboard
        potes.members.add(main, users['demo_player1'], users['demo_player5'], users['demo_newcomer'])

        # Long name league — tests Zone A ellipsis and header word-break.
        long_league, _ = League.objects.get_or_create(
            name=LONG_LEAGUE_NAME,
            defaults={'creator': main},
        )
        long_league.competitions.add(comp)
        long_league.members.add(main, users['demo_player4'])

        # Ended league — linked only to an inactive competition (is_active=False).
        # Tests the "Ended" badge, inactive notice, and league_ended empty_reason.
        ended_league, _ = League.objects.get_or_create(
            name=ENDED_LEAGUE_NAME,
            defaults={'creator': main},
        )
        ended_league.competitions.add(ended_comp)
        ended_league.members.add(main, users['demo_player6'])

        # 3-comp league — tests chips at exactly the display limit (no +N shown).
        three_comp_league, _ = League.objects.get_or_create(
            name=THREE_COMP_LEAGUE_NAME,
            defaults={'creator': main},
        )
        three_comp_league.competitions.set([comp, extra_comps[0], extra_comps[1]])
        three_comp_league.members.add(main, users['demo_player1'])

        # 6-comp league — tests +3 overflow chip.
        six_comp_league, _ = League.objects.get_or_create(
            name=SIX_COMP_LEAGUE_NAME,
            defaults={'creator': main},
        )
        six_comp_league.competitions.set([comp, *extra_comps])
        six_comp_league.members.add(main, users['demo_player2'])

        # --- Avatar for demo_main (profile avatar vs initials fallback) ---
        # Only generate if no avatar already set — safe to re-run.
        if not main.avatar:
            self._set_demo_avatar(main)

        return created_matches

    def _set_demo_avatar(self, user):
        import io
        from django.core.files.base import ContentFile
        from PIL import Image, ImageDraw

        # 80×80 navy circle on transparent background — minimal PNG, no external assets needed
        size = 80
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # Navy fill (#2B3467)
        draw.ellipse([0, 0, size - 1, size - 1], fill=(43, 52, 103, 255))

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        user.avatar.save('demo_main_avatar.png', ContentFile(buf.read()), save=True)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def _print_summary(self, matches):
        self.stdout.write('\n' + self.style.SUCCESS('=== Demo data seeded ===') + '\n')
        self.stdout.write(f'  Login:         demo_main  /  {MAIN_PASSWORD}')
        self.stdout.write(f'  All demo users share the same password: {MAIN_PASSWORD}')
        self.stdout.write(f'  Usernames:     demo_main, demo_player1 … demo_player19, demo_newcomer\n')
        self.stdout.write(f'  Profile states: demo_no_pronos (empty), demo_no_league (stats, no leagues)\n')
        self.stdout.write(f'  Rankings:      demo_main ~rank 15 globally, rank 1 in league')
        self.stdout.write(f'                 True ties: P8=P9 (top), P2=P6 (rank 17), P3=P7 (rank 19)\n')

        self.stdout.write('  Matches:')
        for match, label in matches:
            self.stdout.write(
                f'    [{match.external_id:3d}]  {label}\n'
                f'           /admin/matches/match/{match.pk}/change/'
            )

        self.stdout.write(
            f'\n  Leagues:'
            f'\n    "{LEAGUE_NAME}"       — demo_main creator, rank 1 (4 members)'
            f'\n    "Demo Liga"                — demo_main creator, all 20 players'
            f'\n    "{MEMBER_LEAGUE_NAME}"            — demo_player1 creator, demo_main member (Leave button)'
            f'\n    "{LONG_LEAGUE_NAME}" — long name, ellipsis test'
            f'\n    "{ENDED_LEAGUE_NAME}"     — inactive comp, Ended badge'
            f'\n    "{THREE_COMP_LEAGUE_NAME}"         — 3 comps, no overflow chip'
            f'\n    "{SIX_COMP_LEAGUE_NAME}"           — 6 comps, +3 overflow chip'
            f'\n\n  To wipe and recreate:'
            f'\n    python manage.py seed_ui_states --reset\n'
        )
