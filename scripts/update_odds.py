import os
import sys
import time
from datetime import datetime

import requests
from google import genai
from google.genai import types
from google.genai.errors import ClientError, ServerError

APP_URL = os.environ['APP_URL']
SYNC_SECRET_TOKEN = os.environ['SYNC_SECRET_TOKEN']
GOOGLE_API_KEY = os.environ['GOOGLE_API_KEY']

auth_headers = {'Authorization': f'Bearer {SYNC_SECRET_TOKEN}'}

submit_odds_tool = types.FunctionDeclaration(
    name="submit_odds",
    description=(
        "Soumet les cotes pour les matchs de rugby. Appelle cet outil une seule fois. "
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

# Search config — uses Google Search grounding (costs per query)
search_config = types.GenerateContentConfig(
    system_instruction=(
        "Tu es un assistant spécialisé dans la collecte de cotes de paris sportifs rugby. "
        "Stratégie de recherche :\n"
        "1. Recherche les cotes 1N2 sur des bookmakers ou agrégateurs (Betclic, Winamax, Unibet, Oddsportal, Bet365, Paddy Power).\n"
        "2. Pour CHAQUE match où tu trouves les 3 cotes réelles et vérifiées, prépare l'entrée.\n"
        "3. Ne jamais inventer ou estimer des cotes.\n"
        "4. OBLIGATOIRE : appelle `submit_odds` avec les cotes trouvées, même si certains matchs manquent."
    ),
    tools=[
        types.Tool(
            google_search=types.GoogleSearch(),
            function_declarations=[submit_odds_tool],
        )
    ],
    tool_config=types.ToolConfig(include_server_side_tool_invocations=True),
    temperature=0.1,
)

# Estimate config — no search, inference only (cheap)
estimate_config = types.GenerateContentConfig(
    system_instruction=(
        "Tu es un expert en rugby. Pour chaque match fourni, estime les probabilités de victoire "
        "domicile / nul / extérieur en te basant sur ta connaissance des équipes, leur niveau, "
        "leur forme récente et l'avantage du terrain.\n"
        "Convertis les probabilités en cotes décimales avec une marge bookmaker de 5% : "
        "cote = (1 / probabilité) × 0.95, arrondie à 2 décimales.\n"
        "Exemple : P(home)=0.55, P(draw)=0.15, P(away)=0.30 → "
        "cote_home=round(1/0.55×0.95,2)=1.73, cote_draw=6.33, cote_away=3.17.\n"
        "OBLIGATOIRE : appelle `submit_odds` pour tous les matchs fournis."
    ),
    tools=[types.Tool(function_declarations=[submit_odds_tool])],
    temperature=0.2,
)

client = genai.Client(api_key=GOOGLE_API_KEY)


def _extract_odds(chat):
    for message in reversed(chat.get_history()):
        if message.role == "model" and message.parts:
            for part in message.parts:
                if part.function_call and part.function_call.name == "submit_odds":
                    return {e['match_id']: e for e in part.function_call.args.get('odds', [])}
    return {}


def _call_gemini(matches, cfg, label):
    """Build prompt, call Gemini with retries, return dict[match_id -> entry]."""
    n = len(matches)
    lines = [f"Trouve les cotes 1N2 pour ces {n} matchs de rugby.\n"]
    for m in matches:
        dt = datetime.fromisoformat(m['datetime']).strftime('%d/%m/%Y')
        home = f"{m['home_team']} ({m['home_team_short']})"
        away = f"{m['away_team']} ({m['away_team_short']})"
        lines.append(f"- match_id={m['match_id']} : {home} vs {away} ({m['competition']}, le {dt})")
    lines.append(f"\nObjectif : couvrir les {n} matchs. Appelle submit_odds avec tous les résultats.")
    user_message = "\n".join(lines)

    for attempt in range(1, 4):
        try:
            chat = client.chats.create(model="gemini-3.8-flash", config=cfg)
            chat.send_message(user_message)
            break
        except (ServerError, ClientError) as e:
            is_retryable = isinstance(e, ServerError) or (isinstance(e, ClientError) and '429' in str(e))
            if attempt == 3 or not is_retryable:
                raise
            wait = 30 * attempt
            print(f"Gemini erreur {label} (tentative {attempt}/3), retry dans {wait}s : {e}")
            time.sleep(wait)

    return _extract_odds(chat)


# Step 1 — fetch upcoming matches
resp = requests.get(f'{APP_URL}/api/upcoming-matches/', headers=auth_headers, timeout=30)
resp.raise_for_status()
matches = resp.json()

if not matches:
    print("Aucun match à venir dans les 14 prochains jours.")
    sys.exit(0)

print(f"{len(matches)} match(s) à traiter.")

# Step 2 — search for real bookmaker odds (single pass with Google Search)
found = _call_gemini(matches, search_config, "search")
print(f"Recherche : {len(found)} cote(s) trouvée(s).")

# Step 3 — estimate probability-based odds for missing matches (no search, cheap)
missing_matches = [m for m in matches if m['match_id'] not in found]
if missing_matches:
    print(f"Estimation : {len(missing_matches)} match(s) sans cote réelle, calcul probabiliste...")
    estimated = _call_gemini(missing_matches, estimate_config, "estimate")
    found.update(estimated)
    print(f"Estimation : +{len(estimated)} cote(s) calculée(s).")

if not found:
    print("Aucune cote trouvée ou estimée. Aucune mise à jour.")
    sys.exit(0)

# Normalise les cotes en int (Gemini peut renvoyer des floats)
odds_list = [
    {
        'match_id': int(e['match_id']),
        'cote_home': int(e['cote_home']),
        'cote_draw': int(e['cote_draw']),
        'cote_away': int(e['cote_away']),
    }
    for e in found.values()
]
print(f"Cotes prêtes pour {len(odds_list)} match(s).")

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