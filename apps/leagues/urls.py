from django.urls import path
from . import views

app_name = 'leagues'

urlpatterns = [
    path('', views.LeagueListView.as_view(), name='list'),
    path('create/', views.LeagueCreateView.as_view(), name='create'),
    path('join/', views.LeagueJoinView.as_view(), name='join'),
    path('invite/<str:code>/', views.LeaguePublicInviteView.as_view(), name='public_invite'),
    path('<int:pk>/', views.LeagueDetailView.as_view(), name='detail'),
    path('<int:pk>/leave/', views.LeagueLeaveView.as_view(), name='leave'),
]
