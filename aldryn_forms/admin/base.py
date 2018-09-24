# -*- coding: utf-8 -*-
from email.utils import formataddr

from django.contrib import admin
from django.http import HttpResponse
from django.core.urlresolvers import reverse
from django.template.loader import render_to_string
from django.utils import six
from django.utils.translation import ugettext_lazy as _
import zipfile
from io import BytesIO
import os
from django.utils.safestring import mark_safe
from aldryn_forms.models import FormSubmission

if six.PY2:
    str_dunder_method = '__unicode__'
else:
    str_dunder_method = '__str__'


class InputFilter(admin.SimpleListFilter):
    template = 'admin/aldryn_forms/input_filter.html'
    title = _("Name")
    parameter_name = 'name'
    options = set(FormSubmission.objects.all().values_list('name', flat=True))

    def __init__(self, request, params, model, model_admin):
        super().__init__(request, params, model, model_admin)
        self.selected = self.value()

    def lookups(self, request, model_admin):
        # Dummy, required to show the filter.
        return ((),)

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(name__icontains=self.value().strip())
        return queryset

    def choices(self, changelist):
        # Grab only the "all" option.
        all_choices = next(super().choices(changelist))
        all_choices['query_parts'] = (
            (k, v)
            for k, v in changelist.get_filters_params().items()
            if k != self.parameter_name
        )
        yield all_choices


class BaseFormSubmissionAdmin(admin.ModelAdmin):
    date_hierarchy = 'sent_at'
    list_display = [str_dunder_method, 'sent_at', 'language']
    list_filter = [InputFilter, 'language']
    readonly_fields = [
        'file_url',
        'form',
        'user',
        'name',
        'get_data_for_display',
        'language',
        'sent_at',
        'action',
        'get_recipients_for_display',
        'agreed_consents',
    ]
    actions = ['bulk_pdf_download']
    exclude = ['file']

    def file_url(self, obj):
        if obj.file:
            return mark_safe('<a href="' + obj.file.url + '">' + obj.file.name + '</a>')
        return mark_safe('-')

    def bulk_pdf_download(self, request, queryset):
        data_store = BytesIO()
        zf = zipfile.ZipFile(data_store, 'w')
        for form in queryset:
            f_dir, fname = os.path.split(form.file.path)
            zf.write(form.file.path, fname)
        zf.close()
        response = HttpResponse(data_store.getvalue(), content_type="application/x-zip-compressed")
        response['Content-Disposition'] = 'attachment; filename=%s' % 'PDF_export.zip'
        return response

    bulk_pdf_download.short_description = "Download PDF files form selected forms"

    def has_add_permission(self, request):
        return False

    def get_data_for_display(self, obj):
        data = obj.get_form_data()
        html = render_to_string(
            'admin/aldryn_forms/display/submission_data.html',
            {'data': data}
        )
        return html

    get_data_for_display.allow_tags = True
    get_data_for_display.short_description = _('data')

    def get_recipients(self, obj):
        recipients = obj.get_recipients()
        formatted = [formataddr((recipient.name, recipient.email))
                     for recipient in recipients]
        return formatted

    def get_recipients_for_display(self, obj):
        people_list = self.get_recipients(obj)
        html = render_to_string(
            'admin/aldryn_forms/display/recipients.html',
            {'people': people_list},
        )
        return html

    get_recipients_for_display.allow_tags = True
    get_recipients_for_display.short_description = _('people notified')

    def get_urls(self):
        from django.conf.urls import url

        def pattern(regex, fn, name):
            args = [regex, self.admin_site.admin_view(fn)]
            return url(*args, name=self.get_admin_url(name))

        url_patterns = [
            pattern(r'export/$', self.get_form_export_view(), 'export'),
        ]

        return url_patterns + super(BaseFormSubmissionAdmin, self).get_urls()

    def get_admin_url(self, name):
        try:
            model_name = self.model._meta.model_name
        except AttributeError:
            # django <= 1.5 compat
            model_name = self.model._meta.module_name

        url_name = "%s_%s_%s" % (self.model._meta.app_label, model_name, name)
        return url_name

    def get_admin_context(self, form=None, title=None):
        opts = self.model._meta

        context = {
            'media': self.media,
            'has_change_permission': True,
            'opts': opts,
            'root_path': reverse('admin:index'),
            'current_app': self.admin_site.name,
            'app_label': opts.app_label,
        }

        if form:
            context['adminform'] = form
            context['media'] += form.media

        if title:
            context['original'] = title
        return context

    def get_form_export_view(self):
        raise NotImplementedError
