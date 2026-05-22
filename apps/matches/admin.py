from django.contrib import admin
from .models import Competition, Team, Match


@admin.register(Competition)
class CompetitionAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'season', 'scoring_system', 'good_gap_pts', 'is_active')
    list_filter = ('is_active', 'season', 'scoring_system')
    list_editable = ('scoring_system', 'good_gap_pts', 'is_active')
    search_fields = ('name', 'code')


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'short_name', 'slug', 'country')
    search_fields = ('name', 'short_name', 'slug')


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'competition', 'status', 'datetime', 'home_score', 'away_score', 'cote_home', 'cote_draw', 'cote_away')
    list_filter = ('status', 'competition', 'datetime')
    list_editable = ('cote_home', 'cote_draw', 'cote_away')
    search_fields = ('home_team__name', 'away_team__name')
    date_hierarchy = 'datetime'
    raw_id_fields = ('home_team', 'away_team', 'competition')
