from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ('email', 'is_staff', 'is_active', 'is_superuser', 'is_facilitator')
    list_filter = ('is_staff', 'is_superuser', 'is_facilitator')
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Permissions', {'fields': ('is_staff', 'is_active', 'is_superuser', 'is_facilitator', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login',)}),
        ('Administrative Unit', {'fields': ('administrative_unit',)}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'is_staff', 'is_active', 'is_superuser', 'is_facilitator', 'administrative_unit')}
        ),
    )
    search_fields = ('email',)
    ordering = ('email',)