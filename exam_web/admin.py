from django.contrib import admin
from django_better_admin_arrayfield.admin.mixins import DynamicArrayMixin

from exam_web.models import AcademyGroup, UserSession, ExamSession, \
    ExamTicket, Question, Student


@admin.register(AcademyGroup)
class AcademyGroupAdmin(admin.ModelAdmin):
    pass


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    pass


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin, DynamicArrayMixin):
    pass


@admin.register(ExamTicket)
class ExamTicketAdmin(admin.ModelAdmin):
    pass


@admin.register(ExamSession)
class ExamSessionAdmin(admin.ModelAdmin):
    pass


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    pass
