from django.urls import path
from . import views

app_name = 'rankings'

urlpatterns = [
    path('', views.RankingsView.as_view(), name='index'),
]
