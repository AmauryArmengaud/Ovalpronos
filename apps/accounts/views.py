from django.contrib.auth import views as auth_views
from django.urls import reverse_lazy
from django.views.generic import CreateView
from .forms import RegistrationForm
from .models import CustomUser


class RegisterView(CreateView):
    model = CustomUser
    form_class = RegistrationForm
    template_name = 'accounts/register.html'
    success_url = reverse_lazy('accounts:login')
