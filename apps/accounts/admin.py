from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db.models import Count

from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'display_name', 'favorite_team', 'is_staff', 'is_active', 'prediction_count', 'date_joined')
    list_filter = ('is_staff', 'is_active', 'favorite_team')
    search_fields = ('username', 'email', 'display_name')
    fieldsets = UserAdmin.fieldsets + (
        ('Oval\'Pronos', {'fields': ('display_name', 'avatar', 'favorite_team')}),
    )
    actions = ['activate_users', 'deactivate_users']

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _prediction_count=Count('predictions', distinct=True)
        )

    @admin.display(description='Pronos', ordering='_prediction_count')
    def prediction_count(self, obj):
        return obj._prediction_count

    @admin.action(description='Activer les comptes sélectionnés')
    def activate_users(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description='Désactiver les comptes sélectionnés')
    def deactivate_users(self, request, queryset):
        queryset.exclude(pk=request.user.pk).update(is_active=False)
