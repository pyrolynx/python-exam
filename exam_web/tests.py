import random
from datetime import timedelta
from typing import Union, Type, Tuple, List, Dict

from django import http
from django.test import TestCase, Client
from django.utils import timezone

from exam_web import errors
from exam_web.models import Student, AcademyGroup, uuid_str, ExamSession, \
    UserSession, Question, Stage, QuestionType, ExamTicket, ExamStatus


class ApiClient(Client):
    path: str

    def __init__(self, path: str, student: Student = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.student = student
        self.path = path
        self.headers = {'content_type': 'application/json'}
        if student:
            self.cookies['student'] = student.id

    def path_params(self, **params):
        return ApiClient(self.path.format(**params), self.student)

    def get(self, **kwargs):
        return super().get(self.path, data=kwargs, **self.headers)

    def post(self, **json):
        return super().post(self.path, data=json, **self.headers)

    def __call__(self, **kwargs):
        raise AttributeError('Use `get` or `post` methods instead')


class ApiTestCase(TestCase):
    group: AcademyGroup
    student: Student

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.group = AcademyGroup.objects.create(name='test_group')
        cls.student = Student.objects.create(name='test user', group=cls.group)

    @classmethod
    def tearDownClass(cls):
        cls.student.delete()
        cls.group.delete()
        super().tearDownClass()

    def setup_exam_objects(self):
        self.session = ExamSession.objects.create(
            start_time=timezone.now(), duration=timedelta(minutes=40))
        self.student_session = UserSession.objects.create(
            student=self.student, exam_session=self.session)
        self.questions = [
            Question.objects.create(
                stage=Stage.first, type=QuestionType.single, max_score=1,
                text='test single question', options=['a', 'b', 'c']
            ),
            Question.objects.create(
                stage=Stage.first, type=QuestionType.multi, max_score=1,
                text='test multi question', options=['a', 'b', 'c']
            ),
            Question.objects.create(
                stage=Stage.second, type=QuestionType.open, max_score=1,
                text='test open question', options=None,
            ),
        ]
        self.tickets = [
            ExamTicket.objects.create(
                student=self.student, session=self.student_session,
                question=question) for question in self.questions
        ]
        self.ticket_map = {x.id: x for x in self.tickets}

    def teardown_exam_objects(self):
        for ticket in self.tickets:
            ticket.delete()
        for question in self.questions:
            question.delete()
        self.student_session.delete()

    def assertResponseSuccess(self, response: http.HttpResponse):
        content = response.content.decode()
        self.assertEqual(response.status_code, 200,
                         (response.status_code, content))
        content = response.json()
        self.assertIn('result', content, content)
        return content['result']

    def assertResponseError(
            self, response: http.JsonResponse,
            error: Union[errors.APIError, Type[errors.APIError]] = None
    ) -> Tuple[int, str]:
        content = response.json()
        self.assertGreaterEqual(response.status_code, 400,
                                (response.status_code, content))
        self.assertIn('error', content, content)
        if error is not None:
            if isinstance(error, type):
                error = error()
            self.assertEqual(response.status_code, error.status,
                             (response.status_code, content))
            self.assertEqual(content['error'], error.message,
                             (response.status_code, content))
        return response.status_code, content['error']


class TestAuthorize(ApiTestCase):
    authorize: ApiClient

    def setUp(self):
        super().setUp()
        self.authorize = ApiClient('/api/authorize')

    def test_authorized(self):
        response = self.authorize.post(token=self.student.id)
        result = self.assertResponseSuccess(response)

        self.assertEqual(response.cookies['student'].value, self.student.id)

        self.assertEqual(result['name'], self.student.name)
        self.assertEqual(result['group'], self.group.name)
        self.assertEqual(result['id'], self.student.id)

    def test_authorized_unknown_token(self):
        response = self.authorize.post(token=uuid_str())
        self.assertResponseError(response, errors.Unauthorized)

    def test_authorized_invalid_params(self):
        response = self.authorize.post()
        self.assertResponseError(response, errors.InvalidParameter('token'))

        response = self.authorize.post(token=12345678)
        self.assertResponseError(response, errors.InvalidParameter('token'))

        response = self.authorize.get()
        self.assertEqual(response.status_code, 405)


class TestGetExamSessions(ApiTestCase):
    get_exams: ApiClient
    session: ExamSession
    student_session: UserSession
    questions: List[Question]
    tickets: List[ExamTicket]

    def setUp(self):
        super().setUp()
        self.get_exams = ApiClient('/api/exams', student=self.student)
        self.setup_exam_objects()

    def tearDown(self):
        self.teardown_exam_objects()
        super().tearDown()

    def test_get_exams_available(self):
        result = self.assertResponseSuccess(self.get_exams.get())
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        user_session = result[0]
        self.assertEqual(
            user_session['started_at'], self.session.start_time.isoformat())
        self.assertEqual(user_session['duration'],
                         self.session.duration.total_seconds() / 60)
        self.assertEqual(user_session['checked_in'], False)
        self.assertEqual(user_session['finished_at'], None)
        self.assertEqual(user_session['status'], ExamStatus.available.value)
        self.assertEqual(user_session['score'], None)

    def test_get_exams_check_in(self):
        self.student_session.started_at = timezone.now()
        self.student_session.save()

        result = self.assertResponseSuccess(self.get_exams.get())
        user_session = result[0]
        self.assertEqual(user_session['checked_in'], True)

    def test_get_exams_submitted(self):
        now = timezone.now()
        self.student_session.started_at = timezone.now()
        self.student_session.finished_at = now
        self.student_session.save()

        result = self.assertResponseSuccess(self.get_exams.get())
        user_session = result[0]
        self.assertEqual(user_session['finished_at'], now.isoformat())
        self.assertEqual(user_session['status'], ExamStatus.submitted)
        self.assertEqual(user_session['score'], None)

    def test_get_exams_non_available(self):
        self.session.start_time = timezone.now() + self.session.duration
        self.session.save()

        result = self.assertResponseSuccess(self.get_exams.get())
        user_session = result[0]
        self.assertEqual(user_session['started_at'],
                         self.session.start_time.isoformat())
        self.assertEqual(user_session['finished_at'], None)
        self.assertEqual(user_session['status'], ExamStatus.not_available)

    def test_get_exams_unauthorized(self):
        self.get_exams.cookies = {}
        self.assertResponseError(self.get_exams.get(), errors.Unauthorized)

        response = self.get_exams.post()
        self.assertEqual(response.status_code, 405)

    def test_get_exams_score(self):
        for ticket in self.tickets:
            ticket.score = 1.0
            ticket.save()
        result = self.assertResponseSuccess(self.get_exams.get())
        user_session = result[0]
        self.assertEqual(user_session['score'],
                         sum(t.score for t in self.tickets))

        self.tickets[0].score = None
        self.tickets[0].save()
        result = self.assertResponseSuccess(self.get_exams.get())
        user_session = result[0]
        self.assertEqual(user_session['score'], None)


class TestGetExamTickets(ApiTestCase):
    get_exams: ApiClient
    session: ExamSession
    student_session: UserSession
    questions: List[Question]
    tickets: List[ExamTicket]
    ticket_map: Dict[str, ExamTicket]

    def setUp(self):
        super().setUp()
        self.get_exam_questions = \
            ApiClient('/api/tickets', student=self.student)
        self.setup_exam_objects()

    def tearDown(self):
        self.teardown_exam_objects()
        super().tearDown()

    def test_get_exam_questions(self):
        self.assertFalse(self.student_session.check_in)

        result = self.assertResponseSuccess(
            self.get_exam_questions.post(session_id=self.student_session.id))
        self.assertEqual(result['status'], ExamStatus.available)
        self.assertEqual(result['score'], None)
        self.student_session.refresh_from_db()
        self.assertTrue(self.student_session.check_in)

        questions = result['questions']
        self.assertIsInstance(questions, list)
        self.assertEqual(len(questions), len(self.tickets))
        self.assertEqual([x['id'] for x in questions], [
            x.id for x in sorted(self.tickets, key=lambda x: x.question.stage)
        ])
        for question in questions:
            ticket = self.ticket_map[question['id']]
            ticket_question = ticket.question
            self.assertEqual(question.pop('id'), ticket.id)
            view = ticket_question.as_dict
            view.pop('id')
            self.assertEqual(question, view)

    def test_get_exam_questions_already_checked_in(self):
        self.student_session.check_in = True
        checkin_date = self.student_session.started_at

        result = self.assertResponseSuccess(
            self.get_exam_questions.post(session_id=self.student_session.id))
        self.assertEqual(result['status'], ExamStatus.available)
        self.assertEqual(result['score'], None)
        self.student_session.refresh_from_db()
        self.assertTrue(self.student_session.check_in)
        self.assertEqual(self.student_session.started_at, checkin_date)

        questions = result['questions']
        self.assertIsInstance(questions, list)
        self.assertEqual(len(questions), len(self.tickets))

    def test_get_exam_questions_not_available(self):
        self.session.start_time += self.session.duration
        self.session.save()

        result = self.assertResponseSuccess(
            self.get_exam_questions.post(session_id=self.student_session.id))
        self.assertEqual(result['status'], ExamStatus.not_available)
        self.assertEqual(result['score'], None)

        questions = result['questions']
        self.assertIsInstance(questions, list)
        self.assertEqual(len(questions), 0)

    def test_get_exam_questions_submitted(self):
        self.student_session.finished_at = timezone.now()
        self.student_session.save()
        ANSWER = 'answer'
        for ticket in self.tickets:
            ticket.answer = ANSWER
            ticket.save()

        result = self.assertResponseSuccess(
            self.get_exam_questions.post(session_id=self.student_session.id))
        self.assertEqual(result['status'], ExamStatus.submitted)
        self.assertEqual(result['score'], None)

        questions = result['questions']
        self.assertIsInstance(questions, list)
        self.assertEqual(len(questions), len(self.tickets))
        for question in questions:
            ticket = self.ticket_map[question['id']]
            ticket.refresh_from_db()
            answer = question.pop('answer')
            self.assertEqual(answer, ticket.answer)
            self.assertEqual(question['score'], None)

    def test_get_exam_questions_submitted_and_scored(self):
        self.student_session.finished_at = timezone.now()
        self.student_session.save()
        ANSWER = 'answer'
        for ticket in self.tickets:
            ticket.answer = ANSWER
            ticket.score = 1.0
            ticket.save()

        result = self.assertResponseSuccess(
            self.get_exam_questions.post(session_id=self.student_session.id))
        self.assertEqual(result['status'], ExamStatus.submitted)
        self.assertEqual(result['score'], sum(t.score for t in self.tickets))

        questions = result['questions']
        self.assertIsInstance(questions, list)
        self.assertEqual(len(questions), len(self.tickets))
        for question in questions:
            ticket = self.ticket_map[question['id']]
            ticket.refresh_from_db()
            self.assertEqual(question['score'], ticket.score)

    def test_get_exam_questions_invalid_params(self):
        self.assertResponseError(self.get_exam_questions.post(),
                                 errors.InvalidParameter('session_id'))
        self.assertResponseError(
            self.get_exam_questions.post(session_id=uuid_str()),
            errors.ExamNotFound)
        self.get_exam_questions.cookies = {}
        self.assertResponseError(
            self.get_exam_questions.post(session_id=self.student_session.id),
            errors.Unauthorized)

        response = self.get_exam_questions.get()
        self.assertEqual(response.status_code, 405)


class TestSubmitExam(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.submit_exam = ApiClient('/api/submit', student=self.student)
        self.setup_exam_objects()

    def tearDown(self):
        self.teardown_exam_objects()
        super().tearDown()

    def test_submit_exam(self):
        answers = {}
        ANSWER = 'answer'
        for ticket in self.tickets:
            if ticket.question.type == QuestionType.single:
                answers[ticket.id] = \
                    random.randint(0, len(ticket.question.options)-1)
            elif ticket.question.type == QuestionType.multi:
                answers[ticket.id] = random.sample(
                    list(range(0, len(ticket.question.options))),
                    k=random.randint(0, len(ticket.question.options))
                )
            else:
                answers[ticket.id] = ANSWER
        result = self.assertResponseSuccess(self.submit_exam.post(
            session_id=self.student_session.id, answers=answers))
        self.assertEqual(result, True)

        self.student_session.refresh_from_db()
        self.assertEqual(self.student_session.status, ExamStatus.submitted)
        for ticket in self.tickets:
            ticket.refresh_from_db()
            if ticket.question.type == QuestionType.single:
                self.assertEqual(
                    ticket.answer, ticket.question.options[answers[ticket.id]])
            elif ticket.question.type == QuestionType.multi:
                self.assertEqual(ticket.answer, ';'.join([
                    ticket.question.options[x]
                    for x in sorted(answers[ticket.id])
                ]))
            self.assertIsNotNone(ticket.answered_at)

    def test_submit_without_any_answer(self):
        result = self.assertResponseSuccess(self.submit_exam.post(
            session_id=self.student_session.id, answers={}))
        self.assertEqual(result, True)
        self.student_session.refresh_from_db()
        self.assertEqual(self.student_session.status, ExamStatus.submitted)
        for ticket in self.tickets:
            ticket.refresh_from_db()
            self.assertIsNone(ticket.answered_at)
            self.assertIsNone(ticket.answer)

    def test_submit_partial_answer_errors(self):
        ANSWER = 'answer'
        answers = {
            # неверный порядковый индекс ответа
            self.tickets[0].id: len(self.tickets[0].question.options),
            # неверный тип ответа
            self.tickets[1].id: 0,
            # корректный ответ
            self.tickets[2].id: ANSWER,
            # неверный ид билета
            uuid_str(): ANSWER,
            # несуществующий тикет
            self.tickets[2].id + 1: ANSWER,
        }
        result = self.assertResponseSuccess(self.submit_exam.post(
            session_id=self.student_session.id, answers=answers))
        self.assertEqual(result, True)
        self.student_session.refresh_from_db()
        self.assertEqual(self.student_session.status, ExamStatus.submitted)
        for ticket in self.tickets:
            ticket.refresh_from_db()
        self.assertIsNone(self.tickets[0].answer)
        self.assertIsNone(self.tickets[0].answered_at)
        self.assertIsNone(self.tickets[1].answer)
        self.assertIsNone(self.tickets[1].answered_at)
        self.assertEqual(self.tickets[2].answer, ANSWER)
        self.assertIsNotNone(self.tickets[2].answered_at)

    def test_submit_errors(self):
        self.assertResponseError(self.submit_exam.post(),
                                 errors.InvalidParameter('session_id'))
        self.assertResponseError(self.submit_exam.post(session_id=123),
                                 errors.InvalidParameter('session_id'))
        self.assertResponseError(self.submit_exam.post(session_id=uuid_str()),
                                 errors.InvalidParameter('answers'))
        self.assertResponseError(
            self.submit_exam.post(session_id=uuid_str(), answers=[]),
            errors.InvalidParameter('answers'))
        self.assertResponseError(
            self.submit_exam.post(session_id=uuid_str(), answers={}),
            errors.ExamNotFound)

        self.session.start_time += self.session.duration
        self.session.save()
        self.assertResponseError(self.submit_exam.post(
            session_id=self.student_session.id, answers={}),
            errors.ExamNotAvailable)
        self.student_session.start_time = timezone.now()
        self.student_session.save()
        self.assertResponseError(self.submit_exam.post(
            session_id=self.student_session.id, answers={}),
            errors.ExamNotAvailable)
