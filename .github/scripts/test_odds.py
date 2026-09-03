"""
Test script — vérifie que Claude trouve bien des côtes Unibet.
Usage : ANTHROPIC_API_KEY=sk-... python .github/scripts/test_odds.py
Pas besoin que Django tourne.
"""
import os
import sys
import json

import anthropic

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
if not ANTHROPIC_API_KEY:
    print("Erreur : variable ANTHROPIC_API_KEY manquante.")
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

# --- Identique au script de prod ---

from datetime import datetime
n = len(TEST_MATCHES)
lines = [f"Trouve les cotes 1N2 pour ces {n} matchs de rugby. Tu dois en couvrir {n} sur {n}.\n"]
for m in TEST_MATCHES:
    dt = datetime.fromisoformat(m['datetime']).strftime('%d/%m/%Y')
    home = f"{m['home_team']} ({m['home_team_short']})"
    away = f"{m['away_team']} ({m['away_team_short']})"
    lines.append(f"- match_id={m['match_id']} : {home} vs {away} ({m['competition']}, le {dt})")
lines.append(
    f"\nAvant d'appeler submit_odds, vérifie que tu as bien {n} entrées. "
    "Si des matchs manquent, fais des recherches supplémentaires ciblées sur ces matchs spécifiques."
)
user_message = "\n".join(lines)

submit_odds_tool = {
    "name": "submit_odds",
    "description": (
        "Soumet les cotes trouvées pour les matchs de rugby. Appelle cet outil une seule fois. "
        "N'inclure que les matchs pour lesquels tu as trouvé les 3 cotes (1, N, 2) réelles et vérifiées. "
        "Cotes converties en entiers : cote_décimale × 10 arrondie. Ex: 1.85 → 19, 3.50 → 35."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "odds": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "match_id": {"type": "integer"},
                        "cote_home": {"type": "integer", "minimum": 11, "maximum": 500},
                        "cote_draw": {"type": "integer", "minimum": 11, "maximum": 500},
                        "cote_away": {"type": "integer", "minimum": 11, "maximum": 500},
                    },
                    "required": ["match_id", "cote_home", "cote_draw", "cote_away"],
                },
            }
        },
        "required": ["odds"],
    },
}

print("Appel Claude API en cours...\n")
client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=4096,
    tools=[
        {"type": "web_search_20250305", "name": "web_search"},
        submit_odds_tool,
    ],
    system=(
        "Tu es un assistant spécialisé dans la collecte de cotes de paris sportifs rugby. "
        "Stratégie de recherche en deux temps :\n"
        "1. Commence par rechercher toutes les cotes d'une journée en une seule requête sur un agrégateur "
        "(rugbyscope.fr, ruedesjoueurs.com, wincomparator.com ou oddschecker.com).\n"
        "2. Pour chaque match dont les 3 cotes (1, N, 2) sont encore manquantes après l'étape 1, "
        "fais une recherche ciblée : '<équipe domicile> <équipe extérieure> cotes rugby bookmaker'.\n"
        "Utilise n'importe quel bookmaker reconnu (Unibet, Betclic, Winamax, PMU, ZEbet, Betway, etc.). "
        "N'inclus un match dans submit_odds QUE si tu as trouvé ses 3 cotes réelles et vérifiées. "
        "Ne jamais inventer ou estimer des cotes. Appelle submit_odds exactement une fois."
    ),
    messages=[{"role": "user", "content": user_message}],
)

# Affiche tous les blocs pour voir ce que Claude a fait
print("=== Réponse brute de Claude ===")
for block in response.content:
    if block.type == 'text':
        print(f"[text] {block.text}")
    elif block.type == 'tool_use':
        print(f"[tool_use] {block.name}")
        print(json.dumps(block.input, indent=2, ensure_ascii=False))

# Extrait submit_odds
odds_payload = None
for block in response.content:
    if block.type == 'tool_use' and block.name == 'submit_odds':
        odds_payload = block.input
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

print(f"\nUsage tokens : input={response.usage.input_tokens}, output={response.usage.output_tokens}")
