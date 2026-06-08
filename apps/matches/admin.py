from django.contrib import admin
from django.db.models import Count
from django.urls import reverse
from django.utils.html import format_html

from .models import Competition, Match, Team


# ─── Inline ───────────────────────────────────────────────────────────────────

class PredictionInline(admin.TabularInline):
    """Read-only list of predictions on the Match change page."""
    from apps.predictions.models import Prediction
    model = Prediction
    extra = 0
    fields = ('user', 'predicted_home_score', 'predicted_away_score', 'points_earned', 'result_type')
    readonly_fields = ('user', 'predicted_home_score', 'predicted_away_score', 'points_earned', 'result_type')
    can_delete = False
    show_change_link = False
    max_num = 0

    def has_add_permission(self, request, obj=None):
        return False


# ─── Filters ──────────────────────────────────────────────────────────────────

class UpcomingMatchFilter(admin.SimpleListFilter):
    """Pre-select SCHEDULED matches; pass ?upcoming=all to see every status."""
    title = "Statut (défaut : à venir)"
    parameter_name = "upcoming"

    def lookups(self, request, model_admin):
        return [
            ('all', 'Tous les matchs'),
            ('scheduled', 'À venir (SCHEDULED)'),
            ('finished', 'Terminés (FINISHED)'),
            ('no_odds', 'Sans cotes'),
        ]

    def queryset(self, request, queryset):
        if self.value() == 'all':
            return queryset
        if self.value() == 'finished':
            return queryset.filter(status='FINISHED')
        if self.value() == 'no_odds':
            return queryset.filter(status='SCHEDULED', cote_home__isnull=True)
        # Default (value is None or 'scheduled'): show only SCHEDULED
        return queryset.filter(status='SCHEDULED')


# ─── Competition ──────────────────────────────────────────────────────────────

@admin.register(Competition)
class CompetitionAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'season', 'scoring_system', 'good_gap_pts', 'is_active', 'match_count', 'sync_button')
    list_filter = ('is_active', 'season', 'scoring_system')
    list_editable = ('scoring_system', 'good_gap_pts', 'is_active')
    search_fields = ('name', 'code')
    actions = ['sync_competition_action', 'recalculate_all_scores_action']

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_match_count=Count('matches'))

    @admin.display(description='Matchs', ordering='_match_count')
    def match_count(self, obj):
        return obj._match_count

    @admin.display(description='')
    def sync_button(self, obj):
        url = f'/admin/matches/competition/{obj.pk}/import/'
        return format_html('<a class="button btn btn-sm btn-outline-primary" href="{}">Sync</a>', url)

    @admin.action(description='Synchroniser les matchs depuis l\'API')
    def sync_competition_action(self, request, queryset):
        from apps.matches.services import sync_competition_matches
        for comp in queryset:
            try:
                created, updated = sync_competition_matches(comp.code)
                self.message_user(request, f"{comp.name} : {created} créés, {updated} mis à jour.")
            except Exception as e:
                self.message_user(request, f"{comp.name} : erreur — {e}", level='error')

    @admin.action(description='Recalculer les points (matchs terminés)')
    def recalculate_all_scores_action(self, request, queryset):
        from apps.matches.services import _calculate_points_for_match
        total = 0
        for comp in queryset:
            for match in Match.objects.filter(competition=comp, status='FINISHED'):
                _calculate_points_for_match(match)
                total += 1
        self.message_user(request, f"Recalcul terminé pour {total} match(s).")


# ─── Team ─────────────────────────────────────────────────────────────────────

@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'short_name', 'slug', 'country', 'fan_count')
    search_fields = ('name', 'short_name', 'slug')

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_fan_count=Count('fans'))

    @admin.display(description='Fans', ordering='_fan_count')
    def fan_count(self, obj):
        return obj._fan_count


# ─── Match ────────────────────────────────────────────────────────────────────

_STATUS_STYLES = {
    'SCHEDULED': ('var(--color-primary)', 'var(--color-text-on-primary)', 'À venir'),
    'IN_PLAY':   ('var(--color-brand-rugby)', 'var(--color-text-on-primary)', 'En cours'),
    'FINISHED':  ('var(--color-surface-raised)', 'var(--color-text)', 'Terminé'),
    'POSTPONED': ('#ffc107', '#705500', 'Reporté'),
    'CANCELLED': ('var(--color-accent)', 'var(--color-text-on-primary)', 'Annulé'),
}


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'competition', 'round', 'status_badge', 'datetime', 'score_display', 'has_odds_badge', 'cote_home', 'cote_draw', 'cote_away', 'prediction_count')
    list_filter = (UpcomingMatchFilter, 'competition', 'is_hidden')
    list_editable = ('cote_home', 'cote_draw', 'cote_away')
    search_fields = ('home_team__name', 'away_team__name', 'venue', 'round')
    date_hierarchy = 'datetime'
    raw_id_fields = ('home_team', 'away_team', 'competition')
    actions = ['recalculate_points_action', 'refresh_scores_action', 'mark_hidden', 'mark_visible']
    inlines = [PredictionInline]

    def get_queryset(self, request):
        return (
            super().get_queryset(request)
            .select_related('home_team', 'away_team', 'competition')
            .annotate(_prediction_count=Count('predictions', distinct=True))
        )

    @admin.display(description='Statut')
    def status_badge(self, obj):
        bg, fg, label = _STATUS_STYLES.get(obj.status, ('var(--color-surface-raised)', 'var(--color-text)', obj.status))
        return format_html(
            '<span class="badge-admin" style="background:{};color:{}">{}</span>',
            bg, fg, label,
        )

    @admin.display(description='Score')
    def score_display(self, obj):
        return obj.score_display

    @admin.display(description='Cotes', boolean=False)
    def has_odds_badge(self, obj):
        if obj.has_odds:
            return format_html('<span style="color:#28a745">&#10003;</span>')
        return format_html('<span style="color:#ffc107">&#9888;</span>')

    @admin.display(description='Pronos', ordering='_prediction_count')
    def prediction_count(self, obj):
        return obj._prediction_count

    @admin.action(description='Recalculer les points')
    def recalculate_points_action(self, request, queryset):
        from apps.matches.services import _calculate_points_for_match
        count = 0
        for match in queryset.filter(status='FINISHED'):
            _calculate_points_for_match(match)
            count += 1
        self.message_user(request, f"Points recalculés pour {count} match(s) terminé(s).")

    @admin.action(description='Rafraîchir le cache UserScore')
    def refresh_scores_action(self, request, queryset):
        from apps.matches.services import refresh_user_scores_for_match
        for match in queryset:
            refresh_user_scores_for_match(match)
        self.message_user(request, f"Cache UserScore rafraîchi pour {queryset.count()} match(s).")

    @admin.action(description='Masquer ces matchs')
    def mark_hidden(self, request, queryset):
        queryset.update(is_hidden=True)

    @admin.action(description='Afficher ces matchs')
    def mark_visible(self, request, queryset):
        queryset.update(is_hidden=False)
