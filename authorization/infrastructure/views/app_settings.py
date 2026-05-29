from django.views import View
from django.shortcuts import render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.utils.translation import gettext as _

from src.permissions import IsStaffMemberMixin
from authorization.models import AppSettings


class AppSettingsView(LoginRequiredMixin, IsStaffMemberMixin, View):
    template_name = 'auth/app_settings.html'

    def get(self, request):
        settings = AppSettings.load()
        return render(request, self.template_name, {'app_settings': settings})

    def post(self, request):
        settings = AppSettings.load()
        settings.show_all_activities_button = 'show_all_activities_button' in request.POST
        settings.save()
        messages.success(request, _('Settings saved successfully.'))
        return redirect('authorization:app_settings')
