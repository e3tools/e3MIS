from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, AppSettings


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ('email', 'full_name', 'role', 'commune', 'supervisor', 'is_active', 'is_field_agent')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_field_agent')
    autocomplete_fields = ('supervisor',)
    fieldsets = (
        (None, {'fields': ('email', 'password', 'full_name', 'first_name', 'last_name', 'phone_number')}),
        ('Field monitoring',
         {'fields': ('role', 'supervisor', 'commune', 'region', 'device_class', 'onboarded_on',
                     'preferred_language')}),
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
    search_fields = ('email', 'full_name')
    ordering = ('email',)


@admin.register(AppSettings)
class AppSettingsAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'show_all_activities_button')

    def has_add_permission(self, request):
        return not AppSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
