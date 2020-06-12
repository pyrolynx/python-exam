from django.urls import path

from . import views

app_name = 'tinder'

urlpatterns = [
    path('authorize', views.authorize_student)
]
