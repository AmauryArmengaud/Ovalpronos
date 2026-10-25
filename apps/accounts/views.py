import re
import urllib.request
import urllib.parse
import json
from urllib.parse import urlparse

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout, views as auth_views
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q, Sum
from django.shortcuts import redirect, render
from django.urls import reverse, resolve, Resolver404, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import CreateView, FormView, TemplateView, UpdateView
from django_ratelimit.decorators import ratelimit

from apps.predictions.models import Prediction
from apps.rankings.services import _assign_ranks
from .forms import AccountDeleteForm, EmailOrUsernameAuthenticationForm, ProfileForm, RegistrationForm
from .models import CustomUser, Invitation


def post_field_key(field):
    """Rate-limit key on a POST field. Keyed per account, not per IP: behind nginx
    REMOTE_ADDR is the proxy, so an IP key would throttle every player at once."""
    def key(group, request):
        return request.POST.get(field, '').strip().lower()
    return key


def ratelimited(request, exception):
    return render(request, '429.html', status=429)


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


def _get_invite_league(next_url, request_host):
    """Return the League if next_url points to /leagues/invite/<code>/ and the code exists, else None."""
    if not next_url:
        return None
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request_host}):
        return None
    path = urlparse(next_url).path
    try:
        match = resolve(path)
    except Resolver404:
        return None
    if match.view_name != 'leagues:public_invite':
        return None
    from apps.leagues.models import League
    return League.objects.filter(invite_code=match.kwargs.get('code', '')).first()


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

        # Shared rank — same convention as rankings page (1,1,3 ties)
        all_scores = list(
            Prediction.objects.filter(points_earned__isnull=False)
            .values('user_id')
            .annotate(
                total_points=Sum('points_earned'),
                count_exact=Count('pk', filter=Q(result_type='EXACT')),
                count_gap=Count('pk', filter=Q(result_type='GAP')),
            )
            .order_by('-total_points', '-count_exact', '-count_gap')
        )
        _assign_ranks(all_scores)
        rank_entry = next((e for e in all_scores if e['user_id'] == user.pk), None)
        rank = rank_entry['rank'] if rank_entry else None
        total_ranked = len(all_scores)

        # Leagues with member_count and join_url (mirrors leagues/views.py)
        leagues = list(user.leagues.prefetch_related('competitions', 'members').all())
        for league in leagues:
            league.member_count = len(league.members.all())
            league.join_url = self.request.build_absolute_uri(
                reverse('leagues:public_invite', kwargs={'code': league.invite_code})
            )

        ctx['stats'] = stats
        ctx['rank'] = rank
        ctx['total_ranked'] = total_ranked
        # Show @username only if display_name is set and differs from username
        ctx['show_username'] = bool(user.display_name) and user.display_name != user.username
        ctx['leagues'] = leagues
        return ctx


class ProfileEditView(LoginRequiredMixin, UpdateView):
    model = CustomUser
    form_class = ProfileForm
    template_name = 'accounts/profile_edit.html'
    success_url = reverse_lazy('accounts:profile')

    def get_object(self):
        return self.request.user


class AccountDeleteView(LoginRequiredMixin, FormView):
    template_name = 'accounts/delete.html'
    form_class = AccountDeleteForm

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), 'user': self.request.user}

    def form_valid(self, form):
        from django.utils.translation import gettext as _
        from ovalpronos.analytics import capture
        user = self.request.user
        capture(self.request, 'account_deleted')
        logout(self.request)
        # predictions, scores and memberships cascade; created leagues are handed over
        user.delete()
        messages.success(self.request, _("Your account has been deleted. See you on the pitch!"))
        return redirect('matches:home')


@method_decorator(ratelimit(key=post_field_key('username'), rate='10/m', method='POST'), name='post')
class LoginView(auth_views.LoginView):
    template_name = 'accounts/login.html'
    authentication_form = EmailOrUsernameAuthenticationForm

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['turnstile_site_key'] = settings.TURNSTILE_SITE_KEY
        next_url = self.request.GET.get('next', '')
        ctx['invite_league'] = _get_invite_league(next_url, self.request.get_host())
        return ctx

    def form_valid(self, form):
        response = super().form_valid(form)
        from ovalpronos.analytics import capture
        capture(self.request, 'user_logged_in')
        return response

    def post(self, request, *args, **kwargs):
        token = request.POST.get('cf-turnstile-response', '')
        try:
            ok = _verify_turnstile(token, request.META.get('REMOTE_ADDR', ''))
        except Exception:
            ok = False
        if not ok:
            from django.utils.translation import gettext as _
            messages.error(request, _("CAPTCHA verification failed. Please try again."))
            return self.form_invalid(self.get_form())
        return super().post(request, *args, **kwargs)


class RegisterView(CreateView):
    model = CustomUser
    form_class = RegistrationForm
    template_name = 'accounts/register.html'
    success_url = reverse_lazy('predictions:index')

    def _get_invitation(self):
        token = self.request.POST.get('invite') or self.request.GET.get('invite')
        if not token:
            return None
        return Invitation.objects.filter(token=token, used_at__isnull=True).first()

    def get_initial(self):
        initial = super().get_initial()
        invitation = self._get_invitation()
        if invitation:
            initial.update(
                email=invitation.email,
                display_name=invitation.pseudo,
                # usernames reject spaces, unlike the old app's pseudos
                username=re.sub(r'[^\w.@+-]', '', invitation.pseudo),
            )
        return initial

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        from ovalpronos.analytics import capture
        invitation = self._get_invitation()
        if invitation:
            invitation.used_at = timezone.now()
            invitation.user = self.object
            invitation.save(update_fields=['used_at', 'user'])
            capture(self.request, 'user_registered', {'source': 'invitation', 'cohort': invitation.cohort})
        else:
            capture(self.request, 'user_registered')
        next_url = self.request.POST.get('next') or self.request.GET.get('next')
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={self.request.get_host()}):
            return redirect(next_url)
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['turnstile_site_key'] = settings.TURNSTILE_SITE_KEY
        next_url = self.request.POST.get('next', '') or self.request.GET.get('next', '')
        ctx['next_url'] = next_url
        ctx['invite_league'] = _get_invite_league(next_url, self.request.get_host())
        ctx['invitation'] = self._get_invitation()
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
