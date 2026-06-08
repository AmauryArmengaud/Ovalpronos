from django.contrib import admin
from .models import League, _generate_invite_code


@admin.register(League)
class LeagueAdmin(admin.ModelAdmin):
    list_display = ['name', 'invite_code', 'creator', 'member_count', 'created_at']
    list_filter = ['created_at']
    search_fields = ['name', 'invite_code', 'creator__username']
    readonly_fields = ['invite_code', 'created_at']
    filter_horizontal = ['members']
    actions = ['reset_invite_code']

    def member_count(self, obj):
        return obj.members.count()
    member_count.short_description = 'Members'

    @admin.action(description='Régénérer le code d\'invitation')
    def reset_invite_code(self, request, queryset):
        for league in queryset:
            league.invite_code = _generate_invite_code()
            league.save(update_fields=['invite_code'])
        self.message_user(request, f"Code régénéré pour {queryset.count()} ligue(s).")
