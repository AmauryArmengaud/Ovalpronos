from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.matches.admin_views import CompetitionImportView
from apps.matches.views import sync_scores_api, notify_deadline_reminders_api, notify_results_summary_api

urlpatterns = [
    path('admin/', admin.site.urls),
    path('admin/matches/competition/<int:competition_id>/import/', CompetitionImportView.as_view()),
    path('', include('apps.matches.urls', namespace='matches')),
    path('accounts/', include('apps.accounts.urls', namespace='accounts')),
    path('predictions/', include('apps.predictions.urls', namespace='predictions')),
    path('rankings/', include('apps.rankings.urls', namespace='rankings')),
    path('leagues/', include('apps.leagues.urls', namespace='leagues')),
    path('api/sync-scores/', sync_scores_api),
    path('api/notify/deadline-reminders/', notify_deadline_reminders_api),
    path('api/notify/results-summary/', notify_results_summary_api),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
