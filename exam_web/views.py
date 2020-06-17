import logging
from typing import List

from django.db import transaction
from django.http import HttpRequest, HttpResponseNotAllowed

from exam_web import errors
from exam_web.models import Student, UserSession, ExamStatus, ExamTicket

log = logging.getLogger(__name__)


def check_authorized(func):
    def wrapper(request: HttpRequest, *args, **kwargs):
        try:
            assert 'student' in request.COOKIES and \
                   isinstance(request.COOKIES['student'], str)
            student = Student.get_by_token(request.COOKIES['student'])
            request.session['student'] = student.id
            request.student = student
        except (AssertionError, errors.StudentNotFound):
            raise errors.Unauthorized
        return func(request, *args, **kwargs)

    return wrapper


def check_allowed_methods(methods: List[str]):
    def wrapper(func):
        def args_wrapper(request, *args, **kwargs):
            if request.method not in methods:
                return HttpResponseNotAllowed(methods)
            return func(request, *args, **kwargs)

        return args_wrapper

    return wrapper


@check_allowed_methods(['POST'])
def authorize_student(request: HttpRequest):
    assert 'token' in request.POST, 'token'
    token = request.POST['token']
    assert isinstance(token, str), 'token'

    try:
        student = Student.objects.get(id=token)
    except Student.DoesNotExist:
        raise errors.Unauthorized

    request.session['student'] = student.id
    return student.as_dict


@check_allowed_methods(['GET'])
@check_authorized
def get_exams(request: HttpRequest):
    exam_sessions = []
    for session in request.student.user_sessions.all():
        session: UserSession
        exam_sessions.append({
            'id': session.id,
            'started_at': session.exam_session.start_time.isoformat(),
            'duration': session.exam_session.duration.total_seconds() / 60,
            'checked_in': session.check_in,
            'finished_at': session.finished_at.isoformat()
            if session.finished_at else None,
            'status': session.status,
            'score': session.score,
        })
    return exam_sessions


@check_allowed_methods(['POST'])
@check_authorized
def get_exam_questions(request: HttpRequest):
    assert 'session_id' in request.POST, 'session_id'
    session_id = request.POST['session_id']
    try:
        exam_sheet: UserSession = \
            request.student.user_sessions.filter(id=session_id).get()
    except UserSession.DoesNotExist:
        raise errors.ExamNotFound
    result = {
        'status': ExamStatus.not_available, 'questions': [], 'score': None}
    result['status'] = status = exam_sheet.status
    if status == ExamStatus.available:
        if not exam_sheet.check_in:
            exam_sheet.check_in = True
        result['questions'] = [
            {**ticket.question.as_dict, 'id': ticket.id}
            for ticket in exam_sheet.exam_tickets.order_by('question__stage')
        ]
    elif status == ExamStatus.submitted:
        result['score'] = exam_sheet.score
        result['questions'] = [
            {
                **ticket.question.as_dict,
                'id': ticket.id, 'answer': ticket.answer,
                'score': float(ticket.score) if result['score'] else None
            }
            for ticket in exam_sheet.exam_tickets.order_by('question__stage')
        ]

    return result


@check_authorized
def submit_exam(request: HttpRequest):
    assert 'session_id' in request.POST and \
           isinstance(request.POST['session_id'], str), 'session_id'
    session_id = request.POST['session_id']
    assert 'answers' in request.POST and \
           isinstance(request.POST['answers'], dict), 'answers'

    try:
        exam_sheet: UserSession = \
            request.student.user_sessions.filter(id=session_id).get()
        assert exam_sheet.status == ExamStatus.available
    except UserSession.DoesNotExist:
        raise errors.ExamNotFound
    except AssertionError:
        raise errors.ExamNotAvailable
    with transaction.atomic():
        total_submitions = 0
        ticket_map = {
            ticket.id: ticket for ticket in exam_sheet.exam_tickets.all()}
        answers = request.POST['answers'].items()
        for ticket_id, answer in answers:
            try:
                user_question: ExamTicket = ticket_map[int(ticket_id)]
                user_question.submit(answer)
                total_submitions += 1
            except (KeyError, ValueError):
                log.warning(f'Ticket {ticket_id} not found')
            except AssertionError as e:
                log.warning(f'Ticket{ticket_id} error: {e}')
        exam_sheet.completed = True
    log.info(
        f'Succeeded submissions: {total_submitions},'
        f' errors: {len(answers) - total_submitions}')
    return True
