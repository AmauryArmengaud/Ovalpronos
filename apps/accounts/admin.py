from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'display_name', 'favorite_team', 'is_staff', 'date_joined')
    list_filter = ('is_staff', 'is_active', 'favorite_team')
    search_fields = ('username', 'email', 'display_name')
    fieldsets = UserAdmin.fieldsets + (
        ('Oval\'Pronos', {'fields': ('display_name', 'avatar', 'favorite_team')}),
    )
