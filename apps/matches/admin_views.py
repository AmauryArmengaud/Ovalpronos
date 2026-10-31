from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.views import View
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.utils.translation import gettext as _
from .models import Competition
from .services import campaign_report, sync_competition_matches


@method_decorator(staff_member_required, name='dispatch')
class CompetitionImportView(View):
    def get(self, request, competition_id):
        competition = get_object_or_404(Competition, pk=competition_id)
        return render(request, 'admin/matches/import.html', {'competition': competition})

    def post(self, request, competition_id):
        competition = get_object_or_404(Competition, pk=competition_id)
        r = sync_competition_matches(competition)
        messages.success(
            request,
            _("Sync done for %(name)s: %(created)s created, %(updated)s updated.") % {
                'name': competition.name, 'created': r['created'], 'updated': r['updated']},
        )
        return redirect(reverse('admin:matches_competition_change', args=[competition_id]))


@method_decorator(staff_member_required, name='dispatch')
class CampaignReportView(View):
    def get(self, request, competition_id):
        competition = get_object_or_404(Competition, pk=competition_id)
        try:
            since = parse_date(request.GET.get('since', ''))
        except ValueError:  # well-formed but impossible date, e.g. 2026-02-30
            since = None
        report = campaign_report(competition, since)
        return render(request, 'admin/matches/campaign_report.html', {
            **admin.site.each_context(request),
            'opts': Competition._meta,
            'competition': competition,
            'report': report,
            'title': _("Campaign report"),
        })
