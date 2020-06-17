import uuid
from typing import List
from typing import Union

from django.db import models
from django.utils import timezone
from django_better_admin_arrayfield.models.fields import ArrayField

from exam_web import errors

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


def uuid_str():
    return str(uuid.uuid4())


class AcademyGroup(models.Model):
    name = models.CharField(max_length=CHAR_FIELD_SIZE)

    def __str__(self):
        return self.name


class Student(models.Model):
    id = models.CharField(primary_key=True, default=uuid_str, editable=False,
                          max_length=CHAR_FIELD_SIZE)
    name = models.CharField(max_length=CHAR_FIELD_SIZE)
    group = models.ForeignKey(
        AcademyGroup, on_delete=models.DO_NOTHING, related_name='students',
        null=True,
    )

    @classmethod
    def get_by_token(cls, token: str):
        try:
            return cls.objects.get(id=token)
        except cls.DoesNotExist:
            raise errors.StudentNotFound

    def __str__(self):
        return f'{self.name} ({self.group})'

    @property
    def as_dict(self):
        return {
            'id': self.id,
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
        models.CharField(max_length=CHAR_FIELD_SIZE,), blank=True, null=True)

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

    @property
    def in_progress(self):
        now = timezone.now()
        return self.start_time < now < self.start_time + self.duration


class UserSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    student = models.ForeignKey(
        Student, on_delete=models.DO_NOTHING, related_name='user_sessions')
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    exam_session = models.ForeignKey(
        ExamSession, on_delete=models.DO_NOTHING, related_name='user_sessions')

    class Meta:
        unique_together = ('id', 'student', 'exam_session')

    @property
    def check_in(self):
        return self.started_at is not None

    @check_in.setter
    def check_in(self, value: bool):
        if not self.check_in and value:
            self.started_at = timezone.now()
        elif self.check_in and not value:
            self.started_at = None
        else:
            return
        self.save()

    @property
    def completed(self):
        return self.finished_at is not None

    @completed.setter
    def completed(self, value: bool):
        if not self.completed and value:
            self.finished_at = timezone.now()
        elif self.completed and not value:
            self.finished_at = None
        else:
            return
        self.save()

    @property
    def score(self):
        scores = [ticket.score for ticket in self.exam_tickets.all()]
        if any(x is None for x in scores):
            return None
        return float(sum(scores))

    @property
    def status(self):
        if self.completed:
            return ExamStatus.submitted
        elif self.exam_session.in_progress:
            return ExamStatus.available
        return ExamStatus.not_available


class ExamTicket(models.Model):
    student = models.ForeignKey(
        Student, on_delete=models.DO_NOTHING, related_name='exam_questions',
    )
    session = models.ForeignKey(
        UserSession, on_delete=models.DO_NOTHING, related_name='exam_tickets',
    )
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    answer = models.TextField(null=True, blank=True)
    answered_at = models.DateTimeField(null=True, blank=True)
    score = models.DecimalField(null=True, decimal_places=2, max_digits=4,
                                blank=True)

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
            self.answer = ';'.join(
                self.question.options[x] for x in sorted(answer))
        elif self.question.type == QuestionType.open:
            assert isinstance(
                answer, str,
            ), f'answer must be option index with type str (got {answer})'
            self.answer = answer
        else:
            raise RuntimeError('invalid quetion type')
        self.answered_at = timezone.now()
        self.save()

    class Meta:
        unique_together = ('student', 'session', 'question')
