"""
Test script — vérifie que Gemini trouve bien des côtes de paris sportifs.
Usage : GOOGLE_API_KEY=... python .github/scripts/test_odds.py
Pas besoin que Django tourne.
"""
import os
import sys
import json
from datetime import datetime

from google import genai
from google.genai import types

GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    print("Erreur : variable GOOGLE_API_KEY manquante.")
    sys.exit(1)

# Top 14 2026-2027 — Journée 1
TEST_MATCHES = [
    {
        'match_id': 1,
        'home_team': 'Aviron Bayonnais',
        'home_team_short': 'AB',
        'away_team': 'RC Toulon',
        'away_team_short': 'RCT',
        'competition': 'Top 14',
        'datetime': '2026-09-05T17:05:00+00:00',
    },
    {
        'match_id': 2,
        'home_team': 'Castres Olympique',
        'home_team_short': 'CO',
        'away_team': 'RC Vannes',
        'away_team_short': 'RCV',
        'competition': 'Top 14',
        'datetime': '2026-09-05T17:05:00+00:00',
    },
    {
        'match_id': 3,
        'home_team': 'LOU Rugby',
        'home_team_short': 'LOU',
        'away_team': 'ASM Clermont',
        'away_team_short': 'ASM',
        'competition': 'Top 14',
        'datetime': '2026-09-05T17:05:00+00:00',
    },
    {
        'match_id': 4,
        'home_team': 'Montpellier Hérault Rugby',
        'home_team_short': 'MHR',
        'away_team': 'Section Paloise',
        'away_team_short': 'SP',
        'competition': 'Top 14',
        'datetime': '2026-09-05T17:05:00+00:00',
    },
    {
        'match_id': 5,
        'home_team': 'Stade Français Paris',
        'home_team_short': 'SFP',
        'away_team': 'USA Perpignan',
        'away_team_short': 'USAP',
        'competition': 'Top 14',
        'datetime': '2026-09-05T17:05:00+00:00',
    },
    {
        'match_id': 6,
        'home_team': 'Union Bordeaux-Bègles',
        'home_team_short': 'UBB',
        'away_team': 'Racing 92',
        'away_team_short': 'R92',
        'competition': 'Top 14',
        'datetime': '2026-09-05T19:15:00+00:00',
    },
    {
        'match_id': 7,
        'home_team': 'Stade Rochelais',
        'home_team_short': 'SR',
        'away_team': 'Stade Toulousain',
        'away_team_short': 'ST',
        'competition': 'Top 14',
        'datetime': '2026-09-06T19:05:00+00:00',
    },
]

n = len(TEST_MATCHES)
lines = [f"Trouve les cotes 1N2 pour ces {n} matchs de rugby.\n"]
for m in TEST_MATCHES:
    dt = datetime.fromisoformat(m['datetime']).strftime('%d/%m/%Y')
    home = f"{m['home_team']} ({m['home_team_short']})"
    away = f"{m['away_team']} ({m['away_team_short']})"
    lines.append(f"- match_id={m['match_id']} : {home} vs {away} ({m['competition']}, le {dt})")
lines.append(
    f"\nObjectif : couvrir les {n} matchs. Si après tes recherches ciblées certains manquent encore, "
    "soumets quand même les cotes trouvées — ne reste pas bloqué sur un match introuvable."
)
user_message = "\n".join(lines)

submit_odds_declaration = types.FunctionDeclaration(
    name="submit_odds",
    description=(
        "Soumet les cotes trouvées pour les matchs de rugby. Appelle cet outil une seule fois. "
        "N'inclure que les matchs pour lesquels tu as trouvé les 3 cotes (1, N, 2) réelles et vérifiées. "
        "Cotes converties en entiers : cote_décimale × 10 arrondie. Ex: 1.85 → 19, 3.50 → 35."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "odds": types.Schema(
                type=types.Type.ARRAY,
                items=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "match_id": types.Schema(type=types.Type.INTEGER),
                        "cote_home": types.Schema(type=types.Type.INTEGER, minimum=11, maximum=500),
                        "cote_draw": types.Schema(type=types.Type.INTEGER, minimum=11, maximum=500),
                        "cote_away": types.Schema(type=types.Type.INTEGER, minimum=11, maximum=500),
                    },
                    required=["match_id", "cote_home", "cote_draw", "cote_away"],
                ),
            )
        },
        required=["odds"],
    ),
)

system_instruction = (
    "Tu es un assistant spécialisé dans la collecte de cotes de paris sportifs rugby. "
    "Stratégie de recherche en deux temps :\n"
    "1. Commence par rechercher toutes les cotes d'une journée en une seule requête sur un agrégateur "
    "(rugbyscope.fr, ruedesjoueurs.com, wincomparator.com ou oddschecker.com).\n"
    "2. Pour chaque match dont les 3 cotes (1, N, 2) sont encore manquantes après l'étape 1, "
    "fais une recherche ciblée : '<équipe domicile> <équipe extérieure> cotes rugby bookmaker'.\n"
    "Utilise n'importe quel bookmaker reconnu (Unibet, Betclic, Winamax, PMU, ZEbet, Betway, etc.). "
    "N'inclus un match dans submit_odds QUE si tu as trouvé ses 3 cotes réelles et vérifiées. "
    "Ne jamais inventer ou estimer des cotes. Appelle submit_odds exactement une fois."
)

print("Appel Gemini API en cours...\n")
client = genai.Client(api_key=GOOGLE_API_KEY)
response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents=user_message,
    config=types.GenerateContentConfig(
        system_instruction=system_instruction,
        tools=[
            types.Tool(google_search=types.GoogleSearch()),
            types.Tool(function_declarations=[submit_odds_declaration]),
        ],
        temperature=0.1,
    ),
)

# Extrait submit_odds
odds_payload = None
if response.function_calls:
    for call in response.function_calls:
        if call.name == "submit_odds":
            odds_payload = call.args
            break

print("\n=== Résultat final ===")
if not odds_payload or not odds_payload.get('odds'):
    print("Aucune cote trouvée.")
else:
    for entry in odds_payload['odds']:
        match = next((m for m in TEST_MATCHES if m['match_id'] == entry['match_id']), None)
        label = f"{match['home_team']} vs {match['away_team']}" if match else f"match_id={entry['match_id']}"
        h = entry['cote_home'] / 10
        d = entry['cote_draw'] / 10
        a = entry['cote_away'] / 10
        print(f"  {label} — dom: {h:.2f}  nul: {d:.2f}  ext: {a:.2f}")

print(f"\nUsage tokens : input={response.usage_metadata.prompt_token_count}, output={response.usage_metadata.candidates_token_count}")
