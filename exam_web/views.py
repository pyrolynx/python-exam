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
            assert 'student' not in request.COOKIES or isinstance(request.COOKIES['student'], str)
            student = Student.objects.get(token=request.COOKIES['student'])
            request.session['student'] = student
        except (AssertionError, Student.DoesNotExist):
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
    assert 'token' in request.POST
    token = request.POST['token']
    assert isinstance(token, str)

    try:
        student = Student.objects.get(token=token)
    except Student.DoesNotExist:
        raise errors.Unauthorized

    request.session['student'] = student
    return student.as_dict


@check_allowed_methods(['GET'])
@check_authorized
def get_exam_session(request: HttpRequest):
    student: Student = request.session['student']
    result = {'status': ExamStatus.not_available, 'questions': []}
    try:
        exam_sheet: UserSession = student.exam_sheet.get()
    except UserSession.DoesNotExist:
        return result

    result['status'] = status = exam_sheet.status
    if status == ExamStatus.avaliable:
        result['questions'] = [{**ticket.question.as_dict, 'id': ticket.id}
                               for ticket in exam_sheet.exam_list.order_by(ExamTicket.question.stage)]
    return result


@check_authorized
def submit_exam(request: HttpRequest):
    assert 'answers' in request.POST and isinstance(request.POST['answers'], dict), 'answers'
    student: Student = request.session['student']

    try:
        exam_sheet: UserSession = student.exam_sheet.get()
        assert exam_sheet.status != ExamStatus.available
    except (UserSession.DoesNotExist, AssertionError):
        raise errors.ExamNotAvailable
    with transaction.atomic():
        total_submitions = 0
        ticket_map = {ticket.id: ticket  for ticket in exam_sheet.exam_list}
        answers = request.POST['answers'].items()
        try:
            for ticket_id, answer in answers:
                user_question: ExamTicket = ticket_map[ticket_id]
                user_question.submit(answer)
                total_submitions += 1
        except KeyError:
            log.warning(f'Ticket {ticket_id} not found')
        except AssertionError as e:
            log.warning(f'Ticket{ticket_id} error: {e}')
    log.info(f'Succeeded submissions: {total_submitions}, errors: {len(answers) - total_submitions}')
    return True
