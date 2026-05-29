from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, AppSettings


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ('email', 'is_staff', 'is_active', 'is_superuser', 'is_field_agent')
    list_filter = ('is_staff', 'is_superuser', 'is_field_agent')
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Permissions',
         {'fields': ('is_staff', 'is_active', 'is_superuser', 'is_field_agent', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login',)}),
        ('Administrative Units', {'fields': ('administrative_units',)}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'is_staff', 'is_active', 'is_superuser', 'is_field_agent',
                       'administrative_units')}
         ),
    )
    search_fields = ('email',)
    ordering = ('email',)


@admin.register(AppSettings)
class AppSettingsAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'show_all_activities_button')

    def has_add_permission(self, request):
        return not AppSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
