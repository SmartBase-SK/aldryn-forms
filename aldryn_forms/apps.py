from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _

class FormsConfig(AppConfig):
    label = "aldryn_forms"
    name = "aldryn_forms"
    verbose_name = _("Forms")