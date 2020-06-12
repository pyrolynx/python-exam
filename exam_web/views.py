from django.http import HttpRequest

from exam_web import errors
from exam_web.models import Student, UserSession, ExamStatus


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
        result['questions'] = [ticket.question.as_dict for ticket in exam_sheet.exam_list]
    return result
