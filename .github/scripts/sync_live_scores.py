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

# Step 1 — exit early if no live match
has_live = requests.get(f'{APP_URL}/api/has-live-matches/', headers=auth_headers, timeout=15)
has_live.raise_for_status()
if not has_live.json().get('live'):
    sys.exit(0)

# Step 2 — fetch live matches
resp = requests.get(f'{APP_URL}/api/live-matches/', headers=auth_headers, timeout=15)
resp.raise_for_status()
matches = resp.json()

if not matches:
    sys.exit(0)

print(f"{len(matches)} match(s) en cours.")

# Step 3 — build Gemini prompt
submit_scores_tool = types.FunctionDeclaration(
    name="submit_scores",
    description=(
        "Soumet les scores actuels des matchs de rugby en cours. "
        "Appelle cet outil une seule fois avec tous les matchs trouvés. "
        "Pour chaque match : score domicile, score extérieur, et statut (in_play ou finished)."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "scores": types.Schema(
                type=types.Type.ARRAY,
                items=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "match_id": types.Schema(type=types.Type.INTEGER),
                        "home_score": types.Schema(type=types.Type.INTEGER),
                        "away_score": types.Schema(type=types.Type.INTEGER),
                        "status": types.Schema(
                            type=types.Type.STRING,
                            enum=["in_play", "finished"],
                            description="in_play si le match est en cours, finished si le score est final",
                        ),
                    },
                    required=["match_id", "home_score", "away_score", "status"],
                ),
            )
        },
        required=["scores"],
    ),
)

lines = ["Scores en temps réel pour ces matchs de rugby (kickoff aujourd'hui) :\n"]
for m in matches:
    kickoff = datetime.fromisoformat(m['datetime']).strftime('%H:%M')
    current = f"{m['current_home_score']}-{m['current_away_score']}" if m['current_home_score'] is not None else "inconnu"
    lines.append(
        f"- match_id={m['match_id']} : {m['home_team_short']} vs {m['away_team_short']}"
        f" ({m['competition']}, {kickoff}) — dernier score connu : {current}"
    )
lines.append("\nSi score introuvable : ne pas l'inclure. OBLIGATOIRE : appeler submit_scores.")
user_message = "\n".join(lines)

config = types.GenerateContentConfig(
    system_instruction=(
        "Trouve les scores rugby actuels via Google Search. "
        "N'invente aucun score. Appelle submit_scores avec les résultats."
    ),
    tools=[
        types.Tool(
            google_search=types.GoogleSearch(),
            function_declarations=[submit_scores_tool],
        )
    ],
    tool_config=types.ToolConfig(
        include_server_side_tool_invocations=True
    ),
    temperature=0,
)

client = genai.Client(api_key=GOOGLE_API_KEY)
chat = client.chats.create(model="gemini-2.5-flash", config=config)
response = chat.send_message(user_message)

# Step 4 — extract submit_scores call
scores_payload = None
for message in reversed(chat.get_history()):
    if message.role == "model" and message.parts:
        for part in message.parts:
            if part.function_call and part.function_call.name == "submit_scores":
                scores_payload = part.function_call.args
                break
        if scores_payload:
            break

if not scores_payload or not scores_payload.get('scores'):
    print("Gemini n'a trouvé aucun score.")
    sys.exit(0)

scores_list = [
    {
        'match_id': int(e['match_id']),
        'home_score': int(e['home_score']),
        'away_score': int(e['away_score']),
        'status': e['status'],
    }
    for e in scores_payload['scores']
]
print(f"Scores trouvés pour {len(scores_list)} match(s).")

# Step 5 — POST to Django
update_resp = requests.post(
    f'{APP_URL}/api/update-scores/',
    headers={**auth_headers, 'Content-Type': 'application/json'},
    json={'scores': scores_list},
    timeout=30,
)
update_resp.raise_for_status()
result = update_resp.json()
print(f"Mis à jour : {result['updated']}")
if result['skipped']:
    print(f"Ignorés : {result['skipped']}")
