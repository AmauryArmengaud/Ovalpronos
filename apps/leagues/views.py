from django import forms
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _
from django.views.generic import CreateView, TemplateView, View

from apps.matches.models import Competition
from apps.predictions.models import Prediction
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
        ctx['leagues'] = self.request.user.leagues.prefetch_related('competitions').all()
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
        messages.success(self.request, _("League created! Your invite code: %(code)s") % {'code': self.object.invite_code})
        return response


class LeagueJoinView(LoginRequiredMixin, View):
    def get(self, request):
        from django.shortcuts import render
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
        return redirect('leagues:detail', pk=league.pk)


class LeagueDetailView(LoginRequiredMixin, TemplateView):
    template_name = 'leagues/detail.html'

    def get_object(self):
        league = get_object_or_404(League, pk=self.kwargs['pk'])
        if self.request.user not in league.members.all():
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        return league

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        league = self.get_object()

        members = league.members.all()
        competition_ids = league.competitions.values_list('pk', flat=True)
        leaderboard = (
            members
            .filter(
                predictions__points_earned__isnull=False,
                predictions__match__competition_id__in=competition_ids,
            )
            .annotate(
                total_points=Sum('predictions__points_earned'),
                count_exact=Count('predictions', filter=Q(
                    predictions__result_type='EXACT',
                    predictions__match__competition_id__in=competition_ids,
                )),
                count_gap=Count('predictions', filter=Q(
                    predictions__result_type='GAP',
                    predictions__match__competition_id__in=competition_ids,
                )),
                count_win=Count('predictions', filter=Q(
                    predictions__result_type='WIN',
                    predictions__match__competition_id__in=competition_ids,
                )),
            )
            .order_by('-total_points', '-count_exact', '-count_gap')
        )

        ranked = []
        for rank, user in enumerate(leaderboard, start=1):
            ranked.append({
                'rank': rank,
                'user': user,
                'total_points': user.total_points or 0,
                'count_exact': user.count_exact,
                'count_gap': user.count_gap,
                'count_win': user.count_win,
                'is_current_user': user.pk == self.request.user.pk,
            })

        ctx['league'] = league
        ctx['leaderboard'] = ranked
        ctx['league_competitions'] = league.competitions.all()
        ctx['is_creator'] = league.creator == self.request.user
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
