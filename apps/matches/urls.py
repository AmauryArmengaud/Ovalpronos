from django.urls import path
from django.views.generic import TemplateView
from . import views

app_name = 'matches'

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('rules/', views.RulesView.as_view(), name='rules'),
    path('competitions/<str:code>/', views.CompetitionLandingView.as_view(), name='competition_landing'),
    path('legal/notice/', TemplateView.as_view(template_name='legal/notice.html'), name='legal_notice'),
    path('legal/privacy/', TemplateView.as_view(template_name='legal/privacy.html'), name='legal_privacy'),
    path('legal/terms/', TemplateView.as_view(template_name='legal/terms.html'), name='legal_terms'),
]
