import re
from io import BytesIO

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from PIL import Image, UnidentifiedImageError

from events.attendance import signature_png
from events.models import Attendance, Event

BANNER_MAX_BYTES = 2 * 1024 * 1024


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ["title", "start_date", "end_date"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "end_date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def clean(self):
        cleaned_data = super().clean()
        start, end = cleaned_data.get("start_date"), cleaned_data.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", _("The last day cannot be before the first day."))
        return cleaned_data


class EventPosterForm(forms.Form):
    banner = forms.FileField(
        label=_("Logo band (image at the top of the poster)"), required=False,
        widget=forms.ClearableFileInput(attrs={"accept": "image/png,image/jpeg"}),
    )
    remove_banner = forms.BooleanField(label=_("Remove the logo band"), required=False)
    poster_color = forms.CharField(label=_("Background colour"), widget=forms.TextInput(attrs={"type": "color"}))

    def clean_banner(self):
        file = self.cleaned_data.get("banner")
        if not file:
            return None
        if file.size > BANNER_MAX_BYTES:
            raise ValidationError(_("The image is larger than 2 MB."))
        data = file.read()
        try:
            image = Image.open(BytesIO(data))
            image.verify()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            raise ValidationError(_("Upload a PNG or JPEG image."))
        if image.format not in ("PNG", "JPEG"):
            raise ValidationError(_("Upload a PNG or JPEG image."))
        return data, f"image/{image.format.lower()}"

    def clean_poster_color(self):
        color = self.cleaned_data["poster_color"]
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            raise ValidationError(_("Pick a colour."))
        return color


class AttendanceForm(forms.Form):
    full_name = forms.CharField(label=_("Full name"), max_length=200)
    gender = forms.ChoiceField(label=_("Gender"), choices=Attendance.Gender.choices, widget=forms.RadioSelect)
    organisation = forms.CharField(label=_("Organisation represented"), max_length=200)
    position = forms.CharField(label=_("Position / title"), max_length=200)
    country = forms.CharField(label=_("Country of origin"), max_length=100)
    city = forms.CharField(label=_("City of origin"), max_length=100)
    email = forms.EmailField(label=_("Email"), required=False)
    phone = forms.CharField(label=_("Phone"), max_length=40, required=False)
    signature = forms.CharField(widget=forms.HiddenInput, required=False)
    # Left empty by people; robots fill it.
    website = forms.CharField(required=False, widget=forms.TextInput(attrs={"autocomplete": "off", "tabindex": "-1"}))

    def clean_phone(self):
        phone = self.cleaned_data["phone"].strip()
        if phone and len(re.sub(r"\D", "", phone)) < 6:
            raise ValidationError(_("Enter a valid phone number."))
        return phone

    def clean_signature(self):
        return signature_png(self.cleaned_data.get("signature"))

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("email") and not cleaned_data.get("phone") and "email" not in self.errors:
            self.add_error("email", _("Give an email or a phone number (at least one)."))
        return cleaned_data
