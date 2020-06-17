from django.urls import path

from . import views

app_name = 'tinder'

urlpatterns = [
    path('authorize', views.authorize_student),
    path('exams', views.get_exams),
    path('tickets', views.get_exam_questions),
    path('submit', views.submit_exam),
]
