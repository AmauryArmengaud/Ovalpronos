import os
import sys
from datetime import datetime

import requests
from google import genai
from google.genai import types

APP_URL = os.environ['APP_URL']
SYNC_SECRET_TOKEN = os.environ['SYNC_SECRET_TOKEN']
GOOGLE_API_KEY = os.environ['GOOGLE_API_KEY']

auth_headers = {'Authorization': f'Bearer {SYNC_SECRET_TOKEN}'}

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

# Step 1 — fetch upcoming matches
resp = requests.get(f'{APP_URL}/api/upcoming-matches/', headers=auth_headers, timeout=30)
resp.raise_for_status()
matches = resp.json()

if not matches:
    print("Aucun match à venir dans les 14 prochains jours.")
    sys.exit(0)

print(f"{len(matches)} match(s) à traiter.")

# Step 2 — build Gemini prompt
n = len(matches)
lines = [f"Trouve les cotes 1N2 pour ces {n} matchs de rugby.\n"]
for m in matches:
    dt = datetime.fromisoformat(m['datetime']).strftime('%d/%m/%Y')
    home = f"{m['home_team']} ({m['home_team_short']})"
    away = f"{m['away_team']} ({m['away_team_short']})"
    lines.append(f"- match_id={m['match_id']} : {home} vs {away} ({m['competition']}, le {dt})")
lines.append(
    f"\nObjectif : couvrir les {n} matchs. Si après tes recherches ciblées certains manquent encore, "
    "soumets quand même les cotes trouvées — ne reste pas bloqué sur un match introuvable."
)
user_message = "\n".join(lines)

config = types.GenerateContentConfig(
    system_instruction=(
        "Tu es un assistant spécialisé dans la collecte de cotes de paris sportifs rugby. "
        "Stratégie de recherche :\n"
        "1. Recherche les cotes 1N2 des matchs demandés sur des bookmakers ou agrégateurs (Betclic, Winamax, Unibet, RueDesJoueurs, etc.).\n"
        "2. Pour CHAQUE match où tu trouves les cotes, prépare l'entrée.\n"
        "3. Ne jamais inventer ou estimer des cotes.\n"
        "4. OBLIGATOIRE : Tu DOIS terminer en appelant la fonction `submit_odds` avec la liste des cotes trouvées, même si certains matchs manquent."
    ),
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

client = genai.Client(api_key=GOOGLE_API_KEY)
chat = client.chats.create(model="gemini-3.6-flash", config=config)
response = chat.send_message(user_message)

# Step 3 — extract submit_odds call from chat history
odds_payload = None
for message in reversed(chat.get_history()):
    if message.role == "model" and message.parts:
        for part in message.parts:
            if part.function_call and part.function_call.name == "submit_odds":
                odds_payload = part.function_call.args
                break
        if odds_payload:
            break

if not odds_payload or not odds_payload.get('odds'):
    print("Gemini n'a trouvé aucune cote. Aucune mise à jour.")
    sys.exit(0)

# Normalise les cotes en int (Gemini peut renvoyer des floats)
odds_list = [
    {
        'match_id': int(e['match_id']),
        'cote_home': int(e['cote_home']),
        'cote_draw': int(e['cote_draw']),
        'cote_away': int(e['cote_away']),
    }
    for e in odds_payload['odds']
]
print(f"Cotes trouvées pour {len(odds_list)} match(s).")

# Step 4 — POST to Django
update_resp = requests.post(
    f'{APP_URL}/api/update-odds/',
    headers={**auth_headers, 'Content-Type': 'application/json'},
    json={'odds': odds_list},
    timeout=30,
)
update_resp.raise_for_status()
result = update_resp.json()
print(f"Mis à jour : {result['updated']}")
if result['skipped']:
    print(f"Ignorés : {result['skipped']}")

# Step 5 — notify admins if matches still have no odds
notify_resp = requests.post(
    f'{APP_URL}/api/notify/missing-odds/',
    headers=auth_headers,
    timeout=30,
)
notify_resp.raise_for_status()
notify_result = notify_resp.json()
if notify_result['missing']:
    print(f"Alerte : {notify_result['missing']} match(s) toujours sans côtes — email envoyé aux admins.")
else:
    print("Tous les matchs à venir ont des côtes.")
