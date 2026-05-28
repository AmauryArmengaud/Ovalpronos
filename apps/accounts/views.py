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
        return ctx


class ProfileEditView(LoginRequiredMixin, UpdateView):
    model = CustomUser
    form_class = ProfileForm
    template_name = 'accounts/profile_edit.html'
    success_url = reverse_lazy('accounts:profile')

    def get_object(self):
        return self.request.user


class RegisterView(CreateView):
    model = CustomUser
    form_class = RegistrationForm
    template_name = 'accounts/register.html'
    success_url = reverse_lazy('accounts:login')
