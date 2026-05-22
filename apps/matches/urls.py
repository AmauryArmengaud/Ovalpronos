from django.urls import path
from . import views

app_name = 'matches'

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('rules/', views.RulesView.as_view(), name='rules'),
]
