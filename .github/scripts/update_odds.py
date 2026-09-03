import os
import sys
from datetime import datetime

import requests
import anthropic

APP_URL = os.environ['APP_URL']
SYNC_SECRET_TOKEN = os.environ['SYNC_SECRET_TOKEN']
ANTHROPIC_API_KEY = os.environ['ANTHROPIC_API_KEY']

auth_headers = {'Authorization': f'Bearer {SYNC_SECRET_TOKEN}'}

# Step 1 — fetch upcoming matches
resp = requests.get(f'{APP_URL}/api/upcoming-matches/', headers=auth_headers, timeout=30)
resp.raise_for_status()
matches = resp.json()

if not matches:
    print("Aucun match à venir dans les 14 prochains jours.")
    sys.exit(0)

print(f"{len(matches)} match(s) à traiter.")

# Step 2 — build Claude prompt
lines = ["Trouve les cotes Unibet France pour ces matchs de rugby :\n"]
for m in matches:
    dt = datetime.fromisoformat(m['datetime']).strftime('%d/%m/%Y')
    home = f"{m['home_team']} ({m['home_team_short']})"
    away = f"{m['away_team']} ({m['away_team_short']})"
    lines.append(f"- match_id={m['match_id']} : {home} vs {away} ({m['competition']}, le {dt})")
lines.append("\nAppelle submit_odds avec toutes les cotes trouvées.")
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
        "Pour chaque match fourni, trouve les cotes 1N2 (victoire domicile / nul / victoire extérieur) "
        "chez n'importe quel bookmaker français ou européen reconnu (Unibet, Betclic, Winamax, PMU, ZEbet, Betway, etc.). "
        "Utilise des agrégateurs comme rugbyscope.fr, ruedesjoueurs.com, oddschecker.com ou wincomparator.com "
        "pour trouver rapidement les cotes disponibles. "
        "Objectif : couvrir TOUS les matchs de la liste. "
        "Pour chaque match, utilise les cotes du bookmaker offrant les meilleures cotes ou le plus fiable. "
        "N'inclus un match dans submit_odds QUE si tu as trouvé ses 3 cotes (1, N, 2) réelles et vérifiées. "
        "Ne jamais inventer ou estimer des cotes. Appelle submit_odds exactement une fois."
    ),
    messages=[{"role": "user", "content": user_message}],
)

# Step 3 — extract submit_odds call
odds_payload = None
for block in response.content:
    if block.type == 'tool_use' and block.name == 'submit_odds':
        odds_payload = block.input
        break

if not odds_payload or not odds_payload.get('odds'):
    print("Claude n'a trouvé aucune cote. Aucune mise à jour.")
    sys.exit(0)

print(f"Cotes trouvées pour {len(odds_payload['odds'])} match(s).")

# Step 4 — POST to Django
update_resp = requests.post(
    f'{APP_URL}/api/update-odds/',
    headers={**auth_headers, 'Content-Type': 'application/json'},
    json=odds_payload,
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
