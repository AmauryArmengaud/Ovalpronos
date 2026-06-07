from django.contrib import admin
from .models import League


@admin.register(League)
class LeagueAdmin(admin.ModelAdmin):
    list_display = ['name', 'invite_code', 'creator', 'member_count', 'created_at']
    list_filter = ['created_at']
    search_fields = ['name', 'invite_code', 'creator__username']
    readonly_fields = ['invite_code', 'created_at']
    filter_horizontal = ['members']

    def member_count(self, obj):
        return obj.members.count()
    member_count.short_description = 'Members'
