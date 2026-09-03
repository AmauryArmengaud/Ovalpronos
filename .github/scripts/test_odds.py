"""
Test script — vérifie que Gemini trouve bien des côtes de paris sportifs.
Usage : GOOGLE_API_KEY=... python .github/scripts/test_odds.py
Pas besoin que Django tourne.
"""
import os
import sys
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


submit_odds_tool = types.FunctionDeclaration(
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
                        "cote_home": types.Schema(type=types.Type.INTEGER, description="Cote équipe domicile * 10"),
                        "cote_draw": types.Schema(type=types.Type.INTEGER, description="Cote match nul * 10"),
                        "cote_away": types.Schema(type=types.Type.INTEGER, description="Cote équipe extérieure * 10"),
                    },
                    required=["match_id", "cote_home", "cote_draw", "cote_away"],
                ),
            )
        },
        required=["odds"],
    ),
)


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

system_instruction = (
    "Tu es un assistant spécialisé dans la collecte de cotes de paris sportifs rugby. "
    "Stratégie de recherche :\n"
    "1. Recherche les cotes 1N2 des matchs demandés sur des bookmakers ou agrégateurs (Betclic, Winamax, Unibet, RueDesJoueurs, etc.).\n"
    "2. Pour CHAQUE match où tu trouves les cotes, prépare l'entrée.\n"
    "3. Ne jamais inventer ou estimer des cotes.\n"
    "4. OBLIGATOIRE : Tu DOIS terminer en appelant la fonction `submit_odds` avec la liste des cotes trouvées, même si certains matchs manquent."
)

config = types.GenerateContentConfig(
    system_instruction=system_instruction,
    tools=[
        types.Tool(
            google_search=types.GoogleSearch(),
            function_declarations=[submit_odds_tool],
        )
    ],
    tool_config=types.ToolConfig(
        include_server_side_tool_invocations=True
    ),
    temperature=0.1,
)

print("Appel Gemini API en cours...\n")
client = genai.Client(api_key=GOOGLE_API_KEY)
chat = client.chats.create(model="gemini-3.6-flash", config=config)
response = chat.send_message(user_message)

odds_payload = None
for message in reversed(chat.get_history()):
    if message.role == "model" and message.parts:
        for part in message.parts:
            if part.function_call and part.function_call.name == "submit_odds":
                odds_payload = part.function_call.args
                break
        if odds_payload:
            break

print("\n=== Résultat final ===")
if not odds_payload or not odds_payload.get('odds'):
    print("Aucune cote trouvée.")
else:
    for entry in odds_payload['odds']:
        match = next((m for m in TEST_MATCHES if m['match_id'] == entry['match_id']), None)
        label = f"{match['home_team']} vs {match['away_team']}" if match else f"match_id={entry['match_id']}"
        h = int(entry['cote_home']) / 10
        d = int(entry['cote_draw']) / 10
        a = int(entry['cote_away']) / 10
        print(f"  {label} — dom: {h:.2f}  nul: {d:.2f}  ext: {a:.2f}")

if response.usage_metadata:
    print(f"\nUsage tokens : input={response.usage_metadata.prompt_token_count}, output={response.usage_metadata.candidates_token_count}")
