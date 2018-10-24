# -*- coding: utf-8 -*-
from datetime import datetime

from PIL import Image
from django import forms
from django.conf import settings
from django.core.files import File
from django.forms.forms import NON_FIELD_ERRORS
from django.shortcuts import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext, ugettext_lazy as _
from sizefield.utils import filesizeformat

from account.models import Consent
from .models import FormSubmission, FormPlugin
from .utils import add_form_error, get_user_model


class FileSizeCheckMixin(object):
    def __init__(self, *args, **kwargs):
        self.max_size = kwargs.pop('max_size', None)
        super(FileSizeCheckMixin, self).__init__(*args, **kwargs)

    def clean(self, *args, **kwargs):
        data = super(FileSizeCheckMixin, self).clean(*args, **kwargs)

        if data is None:
            return

        if self.max_size is not None and data.size > self.max_size:
            raise forms.ValidationError(
                ugettext('File size must be under %(max_size)s. Current file size is %(actual_size)s.') % {
                    'max_size': filesizeformat(self.max_size),
                    'actual_size': filesizeformat(data.size),
                })
        return data


class RestrictedFileField(FileSizeCheckMixin, forms.FileField):
    pass


class RestrictedImageField(FileSizeCheckMixin, forms.ImageField):

    def __init__(self, *args, **kwargs):
        self.max_width = kwargs.pop('max_width', None)
        self.max_height = kwargs.pop('max_height', None)
        super(RestrictedImageField, self).__init__(*args, **kwargs)

    def clean(self, *args, **kwargs):
        data = super(RestrictedImageField, self).clean(*args, **kwargs)

        if data is None or not any([self.max_width, self.max_height]):
            return data

        if hasattr(data, 'image'):
            # Django >= 1.8
            width, height = data.image.size
        else:
            width, height = Image.open(data).size
            # cleanup after ourselves
            data.seek(0)

        if self.max_width and width > self.max_width:
            raise forms.ValidationError(
                ugettext(
                    'Image width must be under %(max_size)s pixels. '
                    'Current width is %(actual_size)s pixels.'
                ) % {
                    'max_size': self.max_width,
                    'actual_size': width,
                })

        if self.max_height and height > self.max_height:
            raise forms.ValidationError(
                ugettext(
                    'Image height must be under %(max_size)s pixels. '
                    'Current height is %(actual_size)s pixels.'
                ) % {
                    'max_size': self.max_height,
                    'actual_size': height,
                })

        return data


class FormSubmissionBaseForm(forms.Form):
    # these fields are internal.
    # by default we ignore all hidden fields when saving form data to db.
    language = forms.ChoiceField(
        choices=settings.LANGUAGES,
        widget=forms.HiddenInput()
    )
    form_plugin_id = forms.IntegerField(widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        self.form_plugin = kwargs.pop('form_plugin')
        self.request = kwargs.pop('request')
        super(FormSubmissionBaseForm, self).__init__(*args, **kwargs)
        language = self.form_plugin.language

        send_at = datetime.now() if 'save-button' not in self.request.POST else None
        user = self.request.user if self.request.user.is_authenticated else None
        action = 'submit'
        if self.request.method == 'POST':
            if 'save-button' in self.request.POST or not self.is_valid():
                action = 'save'

        self.instance = FormSubmission(
            user=user,
            form=self.form_plugin,
            action=action,
            name=self.form_plugin.name,
            language=language,
            form_url=self.request.build_absolute_uri(self.request.path),
            sent_at=send_at
        )
        self.fields['language'].initial = language
        self.fields['form_plugin_id'].initial = self.form_plugin.pk

    def _add_error(self, message, field=NON_FIELD_ERRORS):
        try:
            self._errors[field].append(message)
        except KeyError:
            self._errors[field] = self.error_class([message])

    def get_serialized_fields(self, is_confirmation=False):
        """
        The `is_confirmation` flag indicates if the data will be used in a
        confirmation email sent to the user submitting the form or if it will be
        used to render the data for the recipients/admin site.
        """
        for field in self.form_plugin.get_form_fields():
            plugin = field.plugin_instance.get_plugin_class_instance()
            # serialize_field can be None or SerializedFormField  namedtuple instance.
            # if None then it means we shouldn't serialize this field.
            serialized_field = plugin.serialize_field(self, field, is_confirmation)

            if serialized_field:
                yield serialized_field

    def get_serialized_field_choices(self, is_confirmation=False):
        """Renders the form data in a format suitable to be serialized.
        """
        fields = self.get_serialized_fields(is_confirmation)
        fields = [(field.label, field.value) for field in fields]
        return fields

    def get_cleaned_data(self, is_confirmation=False):
        fields = self.get_serialized_fields(is_confirmation)
        form_data = dict((field.name, field.value) for field in fields)
        return form_data

    def save(self, commit=False):
        if self.request.user.is_authenticated:
            pdf_file = getattr(self, 'generated_file', None)
            if pdf_file:
                self.instance.file.save(pdf_file['relative_path'], File(open(pdf_file['path'], 'rb')))
            qs = FormSubmission.objects.filter(user=self.request.user, action='save', form=self.form_plugin)
            if not self.is_valid():
                qs.filter(sent_at__isnull='save-button' in self.request.POST)
            qs.delete()
        self.instance.set_form_data(self)
        if hasattr(self, 'consents_form') and 'save-button' not in self.request.POST:
            self.instance.agreed_consents = self.consents_form.get_agreed_consents()
        if hasattr(self, 'processing_form') and 'save-button' not in self.request.POST:
            self.instance.processing_center = self.processing_form.cleaned_data['center']
        self.instance.save()


class ExtandableErrorForm(forms.ModelForm):

    def append_to_errors(self, field, message):
        add_form_error(form=self, message=message, field=field)


class FormPluginForm(ExtandableErrorForm):

    def __init__(self, *args, **kwargs):
        super(FormPluginForm, self).__init__(*args, **kwargs)

        if (getattr(settings, 'ALDRYN_FORMS_SHOW_ALL_RECIPIENTS', False) and
                'recipients' in self.fields):
            self.fields['recipients'].queryset = get_user_model().objects.all()

    def clean(self):
        redirect_type = self.cleaned_data.get('redirect_type')
        redirect_page = self.cleaned_data.get('redirect_page')
        url = self.cleaned_data.get('url')

        if redirect_type:
            if redirect_type == FormPlugin.REDIRECT_TO_PAGE:
                if not redirect_page:
                    self.append_to_errors('redirect_page', _('Please provide CMS page for redirect.'))
                self.cleaned_data['url'] = None

            if redirect_type == FormPlugin.REDIRECT_TO_URL:
                if not url:
                    self.append_to_errors('url', _('Please provide an absolute URL for redirect.'))
                self.cleaned_data['redirect_page'] = None
        else:
            self.cleaned_data['url'] = None
            self.cleaned_data['redirect_page'] = None

        return self.cleaned_data


class BooleanFieldForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        if 'instance' not in kwargs:  # creating new one
            initial = kwargs.pop('initial', {})
            initial['required'] = False
            kwargs['initial'] = initial
        super(BooleanFieldForm, self).__init__(*args, **kwargs)

    class Meta:
        fields = ['label', 'help_text', 'required', 'required_message']


class SelectFieldForm(forms.ModelForm):
    class Meta:
        fields = ['label', 'help_text', 'required', 'required_message']


class RadioFieldForm(forms.ModelForm):
    class Meta:
        fields = ['label', 'help_text', 'required', 'required_message']


class CaptchaFieldForm(forms.ModelForm):
    class Meta:
        # captcha is always required
        fields = ['label', 'help_text', 'required_message']


class ButtonForm(forms.ModelForm):
    class Meta:
        fields = ['label']


class MinMaxValueForm(ExtandableErrorForm):

    def clean(self):
        min_value = self.cleaned_data.get('min_value')
        max_value = self.cleaned_data.get('max_value')
        if min_value and max_value and min_value > max_value:
            self.append_to_errors('min_value', _(u'Min value can not be greater than max value.'))
        return self.cleaned_data


class TextFieldForm(MinMaxValueForm):

    def __init__(self, *args, **kwargs):
        super(TextFieldForm, self).__init__(*args, **kwargs)
        if 'min_value' in self.fields:
            self.fields['min_value'].label = _(u'Min length')
            self.fields['min_value'].help_text = _(u'Required number of characters to type.')

        if 'max_value' in self.fields:
            self.fields['max_value'].label = _(u'Max length')
            self.fields['max_value'].help_text = _(u'Maximum number of characters to type.')
            self.fields['max_value'].required = False

    class Meta:
        fields = ['label', 'placeholder_text', 'help_text',
                  'min_value', 'max_value', 'required', 'required_message']

class HiddenFieldForm(ExtandableErrorForm):
    class Meta:
        fields = ['name', 'initial_value']


class EmailFieldForm(TextFieldForm):

    def __init__(self, *args, **kwargs):
        super(EmailFieldForm, self).__init__(*args, **kwargs)
        self.fields['min_value'].required = False
        self.fields['max_value'].required = False

    class Meta:
        fields = [
            'label',
            'placeholder_text',
            'help_text',
            'min_value',
            'max_value',
            'required',
            'required_message',
            'email_send_notification',
            'email_subject',
            'email_body',
        ]


class FileFieldForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(FileFieldForm, self).__init__(*args, **kwargs)
        self.fields['help_text'].help_text = _(
            'Explanatory text displayed next to input field. Just like this '
            'one. You can use MAXSIZE as a placeholder for the maximum size '
            'configured below.')

    class Meta:
        fields = ['label', 'help_text', 'required', 'required_message', 'upload_to', 'max_size']


class ImageFieldForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(ImageFieldForm, self).__init__(*args, **kwargs)
        self.fields['help_text'].help_text = _(
            'Explanatory text displayed next to input field. Just like this '
            'one. You can use MAXSIZE, MAXWIDTH, MAXHEIGHT as a placeholders '
            'for the maximum file size and dimensions configured below.')

    class Meta:
        fields = FileFieldForm.Meta.fields + ['max_height', 'max_width']


class TextAreaFieldForm(TextFieldForm):

    def __init__(self, *args, **kwargs):
        super(TextAreaFieldForm, self).__init__(*args, **kwargs)
        self.fields['max_value'].required = False

    class Meta:
        fields = ['label', 'placeholder_text', 'help_text', 'text_area_columns',
                  'text_area_rows', 'min_value', 'max_value', 'required', 'required_message']


class MultipleSelectFieldForm(MinMaxValueForm):

    def __init__(self, *args, **kwargs):
        super(MultipleSelectFieldForm, self).__init__(*args, **kwargs)

        self.fields['min_value'].label = _(u'Min choices')
        self.fields['min_value'].help_text = _(u'Required amount of elements to chose.')

        self.fields['max_value'].label = _(u'Max choices')
        self.fields['max_value'].help_text = _(u'Maximum amount of elements to chose.')

    class Meta:
        # 'required' and 'required_message' depend on min_value field validator
        fields = ['label', 'help_text', 'min_value', 'max_value']


class ConsentForm(forms.Form):
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super(ConsentForm, self).__init__(*args, **kwargs)
        self.fields['consents'] = forms.MultipleChoiceField(
            widget=forms.CheckboxSelectMultiple(),
            label=_("Consents"),
            choices=[self.get_label_for_consent(consent) for consent in self.get_client_consents()],
            required=False,
        )

    def clean(self):
        cleaned_data = super(ConsentForm, self).clean()
        for con in self.get_client_consents():
            if 'consents' not in cleaned_data or (con.required and str(con.id) not in cleaned_data['consents']):
                raise forms.ValidationError(_("Consent \"%(name)s\" is required") % {'name': con.title})
        return cleaned_data

    def get_label_for_consent(self, consent):
        client_type = self.user.npcuser.client if hasattr(self.user, 'npcuser') else 'A'
        if client_type == 'A':
            client = 'individual'
        elif client_type == 'B':
            client = 'individual-business'
        elif client_type == 'C':
            client = 'business'
        consent_url = reverse('account:consent', kwargs={'group': client, 'consent': consent.id})
        if consent.required:
            return consent.id, mark_safe(
                '<a href="{}" onclick="window.open(this.href, \'_blank\', \'resizable=no,status=no,location=no,toolbar=no,menubar=no,fullscreen=no,scrollbars=yes,dependent=no\'); return false;" >{}<span class="asteriskField">*</span></a>'.format(
                    consent_url,
                    consent.title))
        else:
            return consent.id, mark_safe(
                '<a href="{}" onclick="window.open(this.href, \'_blank\', \'resizable=no,status=no,location=no,toolbar=no,menubar=no,fullscreen=no,scrollbars=yes,dependent=no\'); return false;" >{}</a>'.format(
                    consent_url, consent.title))

    def get_client_consents(self):
        client = self.user.npcuser.client if hasattr(self.user, 'npcuser') else 'A'
        return Consent.objects.filter(intended_for__iexact=client, used_for=1)

    def get_agreed_consents(self):
        return list(Consent.objects.filter(pk__in=self.cleaned_data['consents']))


class ProcessingCenterForm(forms.Form):
    CENTER_OPTIONS = (
        ('SK-TA', 'Trnavský kraj'),
        ('SK-TC', 'Trenčiansky kraj'),
        ('SK-NI', 'Nitriansky kraj'),
        ('SK-ZI', 'Žilinský kraj'),
        ('SK-BC', 'Banskobystrický kraj'),
        ('SK-PV', 'Prešovský kraj'),
        ('SK-KI', 'Košický kraj'),
    )
    center = forms.ChoiceField(
        label= _("Please choose processing center"),
        help_text="Lorem ipsum dolor sit amet",
        required=True,
        choices=CENTER_OPTIONS,
        widget=forms.RadioSelect()
    )