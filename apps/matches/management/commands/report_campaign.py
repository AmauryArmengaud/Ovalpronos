from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import translation
from django.utils.translation import gettext as _

from apps.matches.models import Competition
from apps.matches.services import campaign_report


class Command(BaseCommand):
    help = "Campaign funnel for a competition landing: views, sign-ups, conversion, activated, leagues, per source."

    def add_arguments(self, parser):
        parser.add_argument('code', help="Competition code, e.g. NATIONS")
        parser.add_argument('--since', help="Start date YYYY-MM-DD (default: first recorded landing view)")

    def handle(self, *args, **options):
        competition = Competition.objects.filter(code__iexact=options['code']).first()
        if competition is None:
            raise CommandError(f"Unknown competition: {options['code']}")
        try:
            since = datetime.strptime(options['since'], '%Y-%m-%d').date() if options['since'] else None
        except ValueError:
            raise CommandError(f"Invalid --since date: {options['since']} (expected YYYY-MM-DD)")

        report = campaign_report(competition, since)
        # Commands run with translations deactivated: print in the site language
        with translation.override(settings.LANGUAGE_CODE):
            title = _("%(name)s campaign since %(date)s") % {'name': competition.name, 'date': report['since']}
            self.stdout.write(title)
            self._write_section(_("Landing page"), report['landing'], with_views=True)
            self._write_section(_("Outside the landing page"), report['other'], with_views=False)

    def _write_section(self, title, section, with_views):
        header = [_("Source")]
        if with_views:
            header += [_("Views"), _("Sign-ups"), _("Conversion")]
        else:
            header += [_("Sign-ups")]
        header += [_("Activated"), _("Leagues created")]

        lines = [header]
        for row in section['rows'] + [{**section['total'], 'source': _("Total")}]:
            cells = [row['source']]
            if with_views:
                conversion = f"{row['conversion']:.1%}" if row['conversion'] is not None else '-'
                cells += [row['views'], row['signups'], conversion]
            else:
                cells += [row['signups']]
            cells += [row['activated'], row['leagues']]
            lines.append([str(cell) for cell in cells])

        widths = [max(len(line[i]) for line in lines) for i in range(len(header))]
        self.stdout.write(f"\n{title}")
        for line in lines:
            # Source left-aligned, figures right-aligned
            self.stdout.write('  '.join(
                cell.ljust(width) if i == 0 else cell.rjust(width)
                for i, (cell, width) in enumerate(zip(line, widths))
            ))
