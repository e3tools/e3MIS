from django import forms
from django.contrib.auth import get_user_model, authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import gettext as _

UserModel = get_user_model()

class EmailAuthenticationForm(AuthenticationForm):
    """
    Base class for authenticating users. Extend this to get a form that accepts
    username/password logins.
    """

    username = None
    email = forms.EmailField(
        label=_('Email'),
        widget=forms.EmailInput(attrs={"autofocus": True})
    )
    password = forms.CharField(
        label=_("Password"),
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    def __init__(self, request=None, *args, **kwargs):
        """
        The 'request' parameter is set for custom authorization use by subclasses.
        The form data comes in via the standard 'data' kwarg.
        """
        self.request = request
        self.user_cache = None
        self.username_field = UserModel._meta.get_field(UserModel.USERNAME_FIELD)
        forms.forms.BaseForm.__init__(self, *args, **kwargs)
        self.fields['password'].label = _('Password')
        self.fields['email'].label = _('Email')

    def clean(self):
        username = self.cleaned_data.get("email")
        password = self.cleaned_data.get("password")

        if username is not None and password:
            self.user_cache = authenticate(
                self.request, username=username, password=password
            )
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            else:
                self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data

