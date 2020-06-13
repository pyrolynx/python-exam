import uuid
from typing import List
from typing import Union

from django.db import models
from django.utils import timezone
from django_better_admin_arrayfield.models.fields import ArrayField

CHAR_FIELD_SIZE = 128


class QuestionType(models.TextChoices):
    single = 'single'
    multi = 'multi'
    open = 'open'


class Stage(models.IntegerChoices):
    first = 1
    second = 2


class ExamStatus(models.TextChoices):
    available = 'available'
    submitted = 'submitted'
    not_available = 'not_available'


class AcademyGroup(models.Model):
    name = models.CharField(max_length=CHAR_FIELD_SIZE)

    def __str__(self):
        return self.name


class Student(models.Model):
    token = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False,
    )
    name = models.CharField(max_length=CHAR_FIELD_SIZE)
    group = models.ForeignKey(
        AcademyGroup, on_delete=models.DO_NOTHING, related_name='students',
        null=True,
    )

    def __str__(self):
        return f'{self.name} ({self.group})'

    @property
    def as_dict(self):
        return {
            'name': self.name,
            'group': self.group.name,
        }


class Question(models.Model):
    stage = models.IntegerField(choices=Stage.choices)
    type = models.CharField(
        max_length=CHAR_FIELD_SIZE,
        choices=QuestionType.choices,
    )
    max_score = models.DecimalField(decimal_places=2, max_digits=4)
    text = models.TextField()
    options = ArrayField(
        models.CharField(
            max_length=CHAR_FIELD_SIZE,
        ), blank=True, null=True,
    )

    def __str__(self):
        return f'{self.text}'

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

    def __str__(self):
        return \
            f'{self.start_time.strftime("%Y-%m-%d %H:%M")} ({self.duration})'


class UserSession(models.Model):
    id = models.UUIDField(primary_key=True)
    student = models.ForeignKey(
        Student, on_delete=models.DO_NOTHING, related_name='exam_sheet',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True)
    finished_at = models.DateTimeField(null=True)
    exam_session = models.ForeignKey(
        ExamSession, on_delete=models.DO_NOTHING, related_name='user_sessions',
    )

    class Meta:
        unique_together = ('id', 'student', 'exam_session')

    @property
    def status(self):
        if self.exam_session.start_time < timezone.now() or \
                self.exam_session.start_time + self.exam_session.duration \
                < timezone.now():
            return ExamStatus.not_available
        elif self.finished_at is not None:
            return ExamStatus.submitted
        return ExamStatus.available


class ExamTicket(models.Model):
    student = models.ForeignKey(
        Student, on_delete=models.DO_NOTHING, related_name='exam_questions',
    )
    session = models.ForeignKey(
        UserSession, on_delete=models.DO_NOTHING, related_name='exam_list',
    )
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    answer = models.TextField(null=True)
    answered_at = models.DateTimeField(null=True)
    score = models.DecimalField(null=True, decimal_places=2, max_digits=4)

    def submit(self, answer: Union[str, int, List[int]]):
        if self.question.type == QuestionType.single:
            assert self.question.options, 'empty options on question'
            # указан порядковый номер
            assert isinstance(
                answer, int,
            ), f'answer must be option index with type int (got {answer})'
            assert answer < len(
                self.question.options,
            ), 'answer index out of option range'
            self.answer = self.question.options[answer]
        elif self.question.type == QuestionType.multi:
            # указаны несколько порядковых номеров
            assert self.question.options, 'empty options on question'
            assert isinstance(answer, list) and all(
                isinstance(x, int) for x in answer), \
                f'answer must be list of option indices index ' \
                f'with type List[int] (got {answer})'
            assert all(x < len(self.question.options)
                       for x in answer), 'answer index out of option range'
            self.answer = ';'.join(self.question.options[x] for x in answer)
        elif self.question.type == QuestionType.open:
            assert isinstance(
                answer, str,
            ), f'answer must be option index with type str (got {answer})'
            self.answer = answer
        else:
            raise RuntimeError('invalid quetion type')
        self.save()

    class Meta:
        unique_together = ('student', 'session', 'question')
