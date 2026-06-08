from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.views import View
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.urls import reverse
from .models import Competition
from .services import sync_competition_matches


@method_decorator(staff_member_required, name='dispatch')
class CompetitionImportView(View):
    def get(self, request, competition_id):
        competition = get_object_or_404(Competition, pk=competition_id)
        return render(request, 'admin/matches/import.html', {'competition': competition})

    def post(self, request, competition_id):
        competition = get_object_or_404(Competition, pk=competition_id)
        created, updated = sync_competition_matches(competition.code)
        messages.success(
            request,
            f"Sync terminée pour {competition.name} : {created} créés, {updated} mis à jour."
        )
        return redirect(reverse('admin:matches_competition_change', args=[competition_id]))
