from django.contrib import admin
from django.utils.translation import gettext_lazy as _, pgettext_lazy

from .models import UserScore


@admin.register(UserScore)
class UserScoreAdmin(admin.ModelAdmin):
    list_display = ('user', 'scope_label', 'rank', 'points', 'prediction_count', 'exact_count', 'gap_count', 'win_count')
    list_filter = ('competition', 'league')
    search_fields = ('user__username', 'user__display_name')
    readonly_fields = ('user', 'competition', 'league', 'points', 'rank', 'prediction_count', 'exact_count', 'gap_count', 'win_count')
    actions = ['refresh_userscore_action']

    @admin.display(description=_("Scope"))
    def scope_label(self, obj):
        if obj.competition is None and obj.league is None:
            return pgettext_lazy("ranking scope", "Global")
        if obj.competition:
            return _("Competition: %(name)s") % {'name': obj.competition.name}
        return _("League: %(name)s") % {'name': obj.league.name}

    @admin.action(description=_("Refresh the UserScore cache"))
    def refresh_userscore_action(self, request, queryset):
        from apps.matches.services import refresh_user_scores_for_match
        from apps.matches.models import Match

        user_ids = queryset.values_list('user_id', flat=True).distinct()
        matches = Match.objects.filter(
            status='FINISHED',
            predictions__user_id__in=user_ids,
        ).distinct()
        for match in matches:
            refresh_user_scores_for_match(match)
        self.message_user(request, _("Cache refreshed for %(count)s entry(ies).") % {'count': queryset.count()})

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
