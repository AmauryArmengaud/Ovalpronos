import csv

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.db.models import Count
from django.http import HttpResponse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import CustomUser, Invitation


class ActivatedFilter(admin.SimpleListFilter):
    """An account is activated once it has saved at least one prediction"""
    title = _("Activated")
    parameter_name = 'activated'

    def lookups(self, request, model_admin):
        return (('yes', _("Yes")), ('no', _("No")))

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(_prediction_count__gt=0)
        if self.value() == 'no':
            return queryset.filter(_prediction_count=0)
        return queryset


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'display_name', 'favorite_team', 'is_staff', 'is_active', 'prediction_count',
                    'activated', 'signup_source', 'signup_medium', 'signup_campaign', 'signup_content', 'date_joined')
    list_filter = ('is_staff', 'is_active', 'favorite_team', ActivatedFilter, 'signup_source', 'signup_medium',
                   'signup_campaign', 'signup_content')
    search_fields = ('username', 'email', 'display_name')
    fieldsets = UserAdmin.fieldsets + (
        ('Oval\'Pronos', {'fields': ('display_name', 'avatar', 'favorite_team', 'signup_source', 'signup_medium', 'signup_campaign', 'signup_content', 'signup_landing_path')}),
    )
    actions = ['activate_users', 'deactivate_users', 'export_attribution_csv']

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _prediction_count=Count('predictions', distinct=True)
        )

    @admin.display(description='Pronos', ordering='_prediction_count')
    def prediction_count(self, obj):
        return obj._prediction_count

    @admin.display(description=_("Activated"), boolean=True, ordering='_prediction_count')
    def activated(self, obj):
        return obj._prediction_count > 0

    @admin.action(description=_("Export sign-up attribution (CSV)"))
    def export_attribution_csv(self, request, queryset):
        # No email or name: the export is for acquisition analysis, not for contacting people
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="signups_{timezone.localdate():%Y%m%d}.csv"'
        response.write('\ufeff')  # BOM so Excel reads UTF-8 accents
        writer = csv.writer(response, delimiter=';')
        writer.writerow([_("ID"), _("Joined"), _("Source"), _("Medium"), _("Campaign"), _("Content"),
                         _("Landing page"), _("Predictions"), _("Activated")])
        for user in queryset.order_by('date_joined'):
            writer.writerow([
                user.pk, timezone.localtime(user.date_joined).strftime('%Y-%m-%d %H:%M'),
                user.signup_source, user.signup_medium, user.signup_campaign, user.signup_content,
                user.signup_landing_path, user._prediction_count, 1 if user._prediction_count else 0,
            ])
        return response

    @admin.action(description='Activer les comptes sélectionnés')
    def activate_users(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description='Désactiver les comptes sélectionnés')
    def deactivate_users(self, request, queryset):
        queryset.exclude(pk=request.user.pk).update(is_active=False)


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ('email', 'pseudo', 'first_name', 'last_name', 'cohort', 'used_at', 'user', 'created_at')
    list_filter = ('cohort', ('used_at', admin.EmptyFieldListFilter))
    search_fields = ('email', 'pseudo', 'first_name', 'last_name')
    readonly_fields = ('token', 'created_at', 'used_at', 'user')
