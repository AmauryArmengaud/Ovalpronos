import urllib.request
import urllib.parse
import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q, Sum
from django.urls import reverse_lazy
from django.views.generic import CreateView, TemplateView, UpdateView

from apps.predictions.models import Prediction
from .forms import ProfileForm, RegistrationForm
from .models import CustomUser


class ProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'accounts/profile.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user

        stats = Prediction.objects.filter(user=user).aggregate(
            total_points=Sum('points_earned'),
            count_exact=Count('pk', filter=Q(result_type='EXACT')),
            count_gap=Count('pk', filter=Q(result_type='GAP')),
            count_win=Count('pk', filter=Q(result_type='WIN')),
            count_miss=Count('pk', filter=Q(result_type='MISS')),
        )
        stats['total_points'] = stats['total_points'] or 0

        # Global rank
        all_scores = (
            Prediction.objects.filter(points_earned__isnull=False)
            .values('user_id')
            .annotate(total=Sum('points_earned'))
            .order_by('-total')
        )
        rank = next((i + 1 for i, s in enumerate(all_scores) if s['user_id'] == user.pk), None)

        ctx['stats'] = stats
        ctx['rank'] = rank
        ctx['leagues'] = user.leagues.all()
        return ctx


class ProfileEditView(LoginRequiredMixin, UpdateView):
    model = CustomUser
    form_class = ProfileForm
    template_name = 'accounts/profile_edit.html'
    success_url = reverse_lazy('accounts:profile')

    def get_object(self):
        return self.request.user


def _verify_turnstile(token, remote_ip):
    data = urllib.parse.urlencode({
        'secret': settings.TURNSTILE_SECRET_KEY,
        'response': token,
        'remoteip': remote_ip,
    }).encode()
    req = urllib.request.Request(
        'https://challenges.cloudflare.com/turnstile/v0/siteverify',
        data=data,
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read()).get('success', False)


class RegisterView(CreateView):
    model = CustomUser
    form_class = RegistrationForm
    template_name = 'accounts/register.html'
    success_url = reverse_lazy('accounts:login')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['turnstile_site_key'] = settings.TURNSTILE_SITE_KEY
        return ctx

    def post(self, request, *args, **kwargs):
        token = request.POST.get('cf-turnstile-response', '')
        try:
            ok = _verify_turnstile(token, request.META.get('REMOTE_ADDR', ''))
        except Exception:
            ok = False
        if not ok:
            from django.utils.translation import gettext as _
            messages.error(request, _("CAPTCHA verification failed. Please try again."))
            self.object = None
            form = self.get_form()
            return self.form_invalid(form)
        return super().post(request, *args, **kwargs)
