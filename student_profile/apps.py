from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class StudentProfileConfig(AppConfig):
    name = 'student_profile'
    verbose_name = _('Hồ sơ học tập & Điểm tín chỉ')
