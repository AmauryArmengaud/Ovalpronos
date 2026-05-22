import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.matches.models import Team

LEGACY_DIR = Path(settings.BASE_DIR) / "legacy" / "teams"
STATIC_TEAMS_DIR = Path(settings.BASE_DIR) / "static" / "img" / "teams"

# (external_id, name, short_name, slug, country, legacy_filename)
TEAMS = [
    (95,  "Aviron Bayonnais",    "BAY", "bayonne",      "France",    "bayonne.png"),
    (96,  "Bordeaux Bègles",     "BOR", "bordeaux",     "France",    "bordeaux.png"),
    (97,  "CA Brive",            "BRI", "brive",        "France",    "brive.png"),
    (98,  "Castres Olympique",   "CAS", "castres",      "France",    "castres.png"),
    (99,  "Clermont",            "ASM", "clermont",     "France",    "clermont.png"),
    (100, "La Rochelle",         "LRO", "larochelle",   "France",    "larochelle.png"),
    (101, "Lyon",                "LOU", "lyon",         "France",    "image_LOU.png"),
    (102, "Montpellier",         "MHR", "montpellier",  "France",    "montpellier.png"),
    (103, "RC Toulonnais",       "TLN", "toulon",       "France",    "toulon.png"),
    (104, "Racing 92",           "RAC", "racing92",     "France",    "racing.png"),
    (105, "Section Paloise",     "PAU", "pau",          "France",    "pau.png"),
    (106, "Stade Français Paris","SFP", "paris",        "France",    "paris.png"),
    (107, "Stade Toulousain",    "STL", "toulouse",     "France",    "toulouse.png"),
    (114, "Grenoble FC",         "GRE", "grenoble",     "France",    "grenoble.png"),
    (120, "Perpignan",           "PER", "perpignan",    "France",    "perpignan.png"),
    (386, "Angleterre",          "ENG", "england",      "England",   "england.png"),
    (387, "France",              "FRA", "france",       "France",    "france.png"),
    (388, "Irlande",             "IRL", "irland",       "Ireland",   "irland.png"),
    (389, "Italie",              "ITA", "italy",        "Italy",     "italy.png"),
    (390, "Ecosse",              "SCO", "scotland",     "Scotland",  "scotland.png"),
    (391, "Pays de Galles",      "WAL", "walles",       "Wales",     "walles.png"),
]


class Command(BaseCommand):
    help = "Create Team records from legacy CSV data and copy logos to static/img/teams/"

    def handle(self, *args, **options):
        STATIC_TEAMS_DIR.mkdir(parents=True, exist_ok=True)

        created = updated = skipped = 0

        for external_id, name, short_name, slug, country, legacy_filename in TEAMS:
            # Copy logo if a legacy file exists
            logo_url = ""
            if legacy_filename:
                src = LEGACY_DIR / legacy_filename
                dest_filename = f"{slug}.png"
                dest = STATIC_TEAMS_DIR / dest_filename
                if src.exists():
                    shutil.copy2(src, dest)
                    logo_url = f"/static/img/teams/{dest_filename}"
                else:
                    self.stdout.write(self.style.WARNING(
                        f"  Logo not found: {src}"
                    ))

            team, was_created = Team.objects.update_or_create(
                external_id=external_id,
                defaults={
                    "name": name,
                    "short_name": short_name,
                    "slug": slug,
                    "country": country,
                    "logo_url": logo_url,
                },
            )

            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f"  Created: {team}"))
            else:
                updated += 1
                self.stdout.write(f"  Updated: {team}")

        self.stdout.write(self.style.SUCCESS(
            f"\nDone — {created} created, {updated} updated, {skipped} skipped."
        ))
