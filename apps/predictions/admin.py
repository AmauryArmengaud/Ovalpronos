from django.contrib import admin
from .models import Prediction


@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    list_display = ('user', 'match', 'predicted_home_score', 'predicted_away_score', 'points_earned', 'result_type', 'updated_at')
    list_filter = ('result_type', 'match__competition', 'match__status')
    search_fields = ('user__username', 'user__display_name')
    readonly_fields = ('user', 'match', 'predicted_home_score', 'predicted_away_score', 'points_earned', 'result_type', 'created_at', 'updated_at')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
