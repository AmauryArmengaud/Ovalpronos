from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import Prediction

_RESULT_STYLES = {
    'EXACT':     ('var(--color-badge-exact)',  'var(--color-badge-exact-text)', 'Exact'),
    'GAP':       ('var(--color-badge-gap)',    'var(--color-text-on-primary)',  'Bon écart'),
    'WIN':       ('var(--color-badge-win)',    'var(--color-badge-win-text)',   'Vainqueur'),
    'MISS':      ('var(--color-badge-miss)',   'var(--color-badge-miss-text)',  'Raté'),
    'CANCELLED': ('var(--color-surface-raised)', 'var(--color-text-secondary)', 'Annulé'),
}


@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    list_display = ('user', 'match_link', 'predicted_score', 'points_earned', 'result_type_badge', 'updated_at')
    list_filter = ('result_type', 'match__competition', 'match__status', 'match__round')
    search_fields = ('user__username', 'user__display_name', 'match__home_team__name', 'match__away_team__name')
    date_hierarchy = 'updated_at'
    readonly_fields = ('user', 'match', 'predicted_home_score', 'predicted_away_score', 'points_earned', 'result_type', 'created_at', 'updated_at')
    actions = ['recalculate_points_action']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'match__home_team', 'match__away_team', 'match__competition')

    @admin.display(description='Match')
    def match_link(self, obj):
        url = reverse('admin:matches_match_change', args=[obj.match_id])
        return format_html('<a href="{}">{}</a>', url, obj.match)

    @admin.display(description='Pronostic')
    def predicted_score(self, obj):
        return f"{obj.predicted_home_score} - {obj.predicted_away_score}"

    @admin.display(description='Résultat')
    def result_type_badge(self, obj):
        if not obj.result_type:
            return '—'
        bg, fg, label = _RESULT_STYLES.get(obj.result_type, ('var(--color-surface-raised)', 'var(--color-text)', obj.result_type))
        return format_html(
            '<span class="badge-admin" style="background:{};color:{}">{}</span>',
            bg, fg, label,
        )

    @admin.action(description='Recalculer les points')
    def recalculate_points_action(self, request, queryset):
        from apps.matches.services import _calculate_points_for_match
        matches = queryset.values_list('match', flat=True).distinct()
        from apps.matches.models import Match
        count = 0
        for match in Match.objects.filter(pk__in=matches, status='FINISHED'):
            _calculate_points_for_match(match)
            count += 1
        self.message_user(request, f"Points recalculés pour {count} match(s).")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
