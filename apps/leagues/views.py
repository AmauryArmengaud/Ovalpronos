from django import forms
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, TemplateView, View

from apps.matches.models import Competition
from apps.rankings.services import _assign_ranks
from .models import League


class LeagueCreateForm(forms.ModelForm):
    competitions = forms.ModelMultipleChoiceField(
        queryset=Competition.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        label=_("Competitions"),
    )

    class Meta:
        model = League
        fields = ['name', 'competitions']


class LeagueListView(LoginRequiredMixin, TemplateView):
    template_name = 'leagues/list.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        leagues = list(
            self.request.user.leagues
            .prefetch_related('competitions', 'members')
            .all()
        )
        for league in leagues:
            league.join_url = self.request.build_absolute_uri(
                reverse('leagues:public_invite', kwargs={'code': league.invite_code})
            )
            # Compute from prefetch cache — annotate(Count('members')) reuses the
            # filter JOIN (WHERE customuser_id = current_user) and always returns 1.
            league.member_count = len(league.members.all())
        ctx['leagues'] = leagues
        return ctx


class LeagueCreateView(LoginRequiredMixin, CreateView):
    model = League
    form_class = LeagueCreateForm
    template_name = 'leagues/create.html'
    success_url = reverse_lazy('leagues:list')

    def form_valid(self, form):
        form.instance.creator = self.request.user
        response = super().form_valid(form)
        self.object.members.add(self.request.user)
        messages.success(
            self.request,
            _("League created! Your invite code: %(code)s") % {'code': self.object.invite_code}
        )
        from ovalpronos.analytics import capture
        capture(self.request.user.pk, 'league_created', {'league_id': self.object.pk})
        return response


class LeagueJoinView(LoginRequiredMixin, View):
    def get(self, request):
        code = request.GET.get('code', '').strip().upper()
        return render(request, 'leagues/join.html', {'initial_code': code})

    def post(self, request):
        code = request.POST.get('invite_code', '').strip().upper()
        try:
            league = League.objects.get(invite_code=code)
        except League.DoesNotExist:
            messages.error(request, _("No league found with code %(code)s.") % {'code': code})
            return redirect('leagues:join')

        if request.user in league.members.all():
            messages.info(request, _("You are already a member of %(name)s.") % {'name': league.name})
        else:
            league.members.add(request.user)
            messages.success(request, _("You joined %(name)s!") % {'name': league.name})
            from ovalpronos.analytics import capture
            capture(request.user.pk, 'league_joined', {'league_id': league.pk})
        return redirect('leagues:detail', pk=league.pk)


class LeaguePublicInviteView(View):
    """Public invite page — GET requires no login. Authenticated users are auto-joined."""

    def get(self, request, code):
        code = code.upper()
        try:
            league = League.objects.prefetch_related('competitions').get(invite_code=code)
        except League.DoesNotExist:
            return render(request, 'leagues/public_invite.html', {'invalid': True})

        if request.user.is_authenticated:
            if not league.members.filter(pk=request.user.pk).exists():
                league.members.add(request.user)
                from ovalpronos.analytics import capture
                capture(request.user.pk, 'league_joined', {'league_id': league.pk, 'via': 'invite_link'})
            return redirect('leagues:detail', pk=league.pk)

        return render(request, 'leagues/public_invite.html', {
            'league': league,
            'code': code,
        })


class LeagueDetailView(LoginRequiredMixin, TemplateView):
    template_name = 'leagues/detail.html'

    def _get_league(self):
        league = get_object_or_404(League, pk=self.kwargs['pk'])
        if self.request.user not in league.members.all():
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        return league

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        league = self._get_league()

        competition_ids = list(league.competitions.values_list('pk', flat=True))

        # All members shown — including those with 0 points (new member visible immediately)
        member_qs = (
            league.members
            .annotate(
                total_points=Coalesce(
                    Sum(
                        'predictions__points_earned',
                        filter=Q(
                            predictions__points_earned__isnull=False,
                            predictions__match__competition_id__in=competition_ids,
                        ),
                    ),
                    0,
                ),
                count_predictions=Count(
                    'predictions',
                    filter=Q(
                        predictions__points_earned__isnull=False,
                        predictions__match__competition_id__in=competition_ids,
                    ),
                ),
                count_exact=Count(
                    'predictions',
                    filter=Q(
                        predictions__result_type='EXACT',
                        predictions__match__competition_id__in=competition_ids,
                    ),
                ),
                count_gap=Count(
                    'predictions',
                    filter=Q(
                        predictions__result_type='GAP',
                        predictions__match__competition_id__in=competition_ids,
                    ),
                ),
                count_win=Count(
                    'predictions',
                    filter=Q(
                        predictions__result_type='WIN',
                        predictions__match__competition_id__in=competition_ids,
                    ),
                ),
            )
            .order_by('-total_points', '-count_exact', '-count_gap', 'username')
        )

        entries = [
            {
                'user': user,
                'total_points': user.total_points,
                'count_predictions': user.count_predictions,
                'count_exact': user.count_exact,
                'count_gap': user.count_gap,
                'count_win': user.count_win,
                'is_current_user': user.pk == self.request.user.pk,
            }
            for user in member_qs
        ]
        _assign_ranks(entries)

        join_url = self.request.build_absolute_uri(
            reverse('leagues:public_invite', kwargs={'code': league.invite_code})
        )

        ctx['league'] = league
        ctx['entries'] = entries
        ctx['empty_reason'] = 'league_ended' if not league.is_active else 'league'
        ctx['league_competitions'] = league.competitions.all()
        ctx['is_creator'] = league.creator == self.request.user
        ctx['join_url'] = join_url
        return ctx


class LeagueLeaveView(LoginRequiredMixin, View):
    def post(self, request, pk):
        league = get_object_or_404(League, pk=pk)
        if request.user in league.members.all():
            if league.creator == request.user:
                messages.error(request, _("The creator cannot leave their own league."))
            else:
                league.members.remove(request.user)
                messages.success(request, _("You left %(name)s.") % {'name': league.name})
        return redirect('accounts:profile')
