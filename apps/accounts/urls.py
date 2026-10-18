from django.conf import settings
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .forms import TrackingFreePasswordResetForm

app_name = 'accounts'

urlpatterns = [
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('profile/edit/', views.ProfileEditView.as_view(), name='profile_edit'),
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path(
        'password-reset/',
        auth_views.PasswordResetView.as_view(
            form_class=TrackingFreePasswordResetForm,
            template_name='accounts/password_reset.html',
            subject_template_name='emails/password_reset_subject.txt',
            email_template_name='emails/password_reset.txt',
            html_email_template_name='emails/password_reset.html',
            extra_email_context={
                'timeout_hours': settings.PASSWORD_RESET_TIMEOUT // 3600,
                'site_url': settings.SITE_URL,
            },
            success_url='/accounts/password-reset/done/',
        ),
        name='password_reset',
    ),
    path(
        'password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(template_name='accounts/password_reset_done.html'),
        name='password_reset_done',
    ),
    path(
        'password-reset-confirm/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='accounts/password_reset_confirm.html',
            success_url='/accounts/password-reset/complete/',
        ),
        name='password_reset_confirm',
    ),
    path(
        'password-reset/complete/',
        auth_views.PasswordResetCompleteView.as_view(template_name='accounts/password_reset_complete.html'),
        name='password_reset_complete',
    ),
]
