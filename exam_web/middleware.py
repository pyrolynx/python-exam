import json
import logging

from django.http import HttpRequest
from django.http.response import HttpResponseBase, JsonResponse
from django.utils.deprecation import MiddlewareMixin

from exam_web.errors import APIError, EmptyResponse, InvalidParameter

log = logging.getLogger('middleware')


class JsonResponseMiddleware(MiddlewareMixin):
    @staticmethod
    def process_request(request: HttpRequest):
        if not request.path.startswith('/api'):
            return
        query_params = dict(request.GET)
        if request.method == 'POST' and \
                request.content_type == 'application/json':
            try:
                query_params.update(json.loads(request.body))
            except (json.JSONDecodeError, UnicodeDecodeError):
                return JsonResponse({'error': 'invalid content'}, status=400)
        request.POST = query_params

    @staticmethod
    def process_response(request: HttpRequest, response):
        if isinstance(response, HttpResponseBase):
            return response

        response = JsonResponse({'result': response})
        if 'student' in request.session and 'student' not in request.COOKIES:
            response.set_cookie('student', request.session['student'])
        return response

    @staticmethod
    def process_exception(request: HttpRequest, exception):
        response_body, status = {'error': APIError.message}, 500
        if isinstance(exception, AssertionError):
            exception = InvalidParameter(str(exception))

        if isinstance(exception, EmptyResponse):
            return JsonResponse({'result': None})
        elif isinstance(exception, APIError):
            response_body['error'], status = \
                exception.message, exception.status
        else:
            log.exception('exception')
            response_body['error'] = f'{type(exception)}: {exception}'

        return JsonResponse(response_body, status=status)
