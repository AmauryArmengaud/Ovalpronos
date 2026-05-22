from django.urls import path

from . import views

app_name = 'predictions'

urlpatterns = [
    path('', views.PredictionsView.as_view(), name='index'),
    path('submit/<int:match_pk>/', views.SubmitPredictionView.as_view(), name='submit'),
]
