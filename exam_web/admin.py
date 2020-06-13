from django.contrib import admin
from django_better_admin_arrayfield.admin.mixins import DynamicArrayMixin

from exam_web.models import AcademyGroup
from exam_web.models import ExamSession
from exam_web.models import ExamTicket
from exam_web.models import Question
from exam_web.models import Student


# Register your models here.


@admin.register(AcademyGroup)
class AcademyGroupAdmin(admin.ModelAdmin):
    pass


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    readonly_fields = ('token',)


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin, DynamicArrayMixin):
    pass


@admin.register(ExamTicket)
class ExamTicketAdmin(admin.ModelAdmin):
    pass


@admin.register(ExamSession)
class ExamSessionAdmin(admin.ModelAdmin):
    pass
