from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils import timezone

CHAR_FIELD_SIZE = 128

QuestionType = models.TextChoices('QuestionType', ['singe', 'multi', 'open'])
Stage = models.IntegerChoices('Stage', ['stage1', 'stage2'])


class ExamStatus(models.TextChoices):
    available = 'available'
    submitted = 'submitted'
    not_available = 'not_available'


class AcademyGroup(models.Model):
    name = models.CharField(max_length=CHAR_FIELD_SIZE)


class Student(models.Model):
    token = models.UUIDField(primary_key=True)
    name = models.CharField(max_length=CHAR_FIELD_SIZE)
    group = models.ForeignKey(AcademyGroup, on_delete=models.DO_NOTHING, related_name='students')

    @property
    def as_dict(self):
        return {
            'name': self.name,
            'group': self.group.name,
        }


class Question(models.Model):
    stage = models.IntegerField(choices=Stage.choices)
    type = models.CharField(max_length=CHAR_FIELD_SIZE, choices=Stage.choices)
    max_score = models.DecimalField(decimal_places=2, max_digits=4)
    text = models.TextField()
    options = ArrayField(models.CharField(max_length=CHAR_FIELD_SIZE), null=True)

    @property
    def as_dict(self):
        return {
            'id': self.id,
            'stage': self.stage,
            'type': self.type,
            'text': self.text,
            'options': self.options,
        }


class ExamSession(models.Model):
    start_time = models.DateTimeField()
    duration = models.DurationField()


class UserSession(models.Model):
    id = models.UUIDField(primary_key=True)
    student = models.ForeignKey(Student, on_delete=models.DO_NOTHING, related_name='exam_sheet')
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True)
    finished_at = models.DateTimeField(null=True)
    exam_session = models.ForeignKey(ExamSession, on_delete=models.DO_NOTHING, related_name='user_sessions')

    class Meta:
        unique_together = ('id', 'student', 'exam_session')

    @property
    def status(self):
        if self.exam_session.start_time < timezone.now() or \
                self.exam_session.start_time + self.exam_session.duration < timezone.now():
            return ExamStatus.not_available
        elif self.finished_at is not None:
            return ExamStatus.submitted
        return ExamStatus.available


class ExamList(models.Model):
    student = models.ForeignKey(Student, on_delete=models.DO_NOTHING, related_name='exam_questions')
    session = models.ForeignKey(UserSession, on_delete=models.DO_NOTHING, related_name='exam_list')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    answer = models.TextField(null=True)
    answered_at = models.DateTimeField(null=True)
    score = models.DecimalField(null=True, decimal_places=2, max_digits=4)

    class Meta:
        unique_together = ('student', 'session', 'question')
