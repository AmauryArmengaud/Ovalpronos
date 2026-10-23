# Surveillance : être prévenu quand quelque chose casse

Trois outils gratuits, alertes par email :

| Quoi | Outil | Tu reçois un email quand… |
|---|---|---|
| Le site répond-il ? | UptimeRobot | le site ne répond plus pendant 5 min |
| Les tâches automatiques ont-elles tourné ? | Healthchecks.io | une tâche plante, ou ne s'est pas lancée à l'heure |
| Les données sont-elles saines ? | Healthchecks.io (tâche `check_business_health`) | un match est resté "à venir" alors qu'il est joué, des pronos sont sans points, un match proche n'a pas de cotes, le disque est presque plein |
| Une page plante-t-elle pour un joueur (erreur 500) ? | PostHog (déjà en place) | il y a eu au moins une erreur dans l'heure |

Aucune donnée personnelle n'est envoyée. PostHog ne reçoit que l'identifiant anonyme `user_<numéro>`, le type d'erreur et la page concernée (sans email, IP ni lien secret).

---

## 1. UptimeRobot (5 min)

1. Créer un compte gratuit sur https://uptimerobot.com.
2. **Add New Monitor** :
   - Monitor Type : **HTTP(s)**
   - Friendly Name : `Oval'Pronos`
   - URL : `https://ovalpronos.com/rules/` (cette page interroge la base : si elle répond, le site et la base fonctionnent)
   - Monitoring Interval : **5 minutes**
3. Dans **Alert Contacts**, cocher ton email.
4. Vérifier : le monitor passe au vert ("Up") en quelques minutes.

## 2. Healthchecks.io (10 min)

1. Créer un compte gratuit sur https://healthchecks.io (20 tâches gratuites, il en faut 5).
2. Créer ces 5 "checks". Pour chacun : **Add Check**, puis **Edit Schedule** → onglet **Cron**, avec le fuseau **UTC** :

| Nom | Cron | Grace time |
|---|---|---|
| `sync-matches` | `0 7 * * *` | 1 hour |
| `sync-live-scores` | `*/10 * * * *` | 15 minutes |
| `update-odds` | `0 10 * * 2` | 2 hours |
| `deadline-reminders` | `0 10 * * *` | 1 hour |
| `business-health` | `0 8 * * *` | 1 hour |

3. Chaque check a une adresse de la forme `https://hc-ping.com/xxxxxxxx-xxxx-...`. Garde les 5 sous la main.
4. Sur le serveur, `crontab -e`, puis remplacer les 4 lignes actuelles par les 6 lignes ci-dessous, en collant chaque adresse à la place de `<URL_...>` :

```bash
SHELL=/bin/bash
W=/home/amaury/Ovalpronos/scripts/ops/cron_wrap.sh
APP="cd /home/amaury/Ovalpronos && set -a && source .env && set +a && source venv/bin/activate"
0 7 * * * $W <URL_sync-matches> bash -c "$APP && python manage.py sync_matches" >> /home/amaury/logs/sync_daily.log 2>&1
*/10 * * * * $W <URL_sync-live-scores> bash -c "$APP && python scripts/sync_live_scores.py" >> /home/amaury/logs/sync_live.log 2>&1
0 10 * * 2 $W <URL_update-odds> bash -c "$APP && python scripts/update_odds.py" >> /home/amaury/logs/update_odds.log 2>&1
0 10 * * * $W <URL_deadline-reminders> bash -c "$APP && python manage.py send_deadline_reminders" >> /home/amaury/logs/email_notifications.log 2>&1
0 8 * * * $W <URL_business-health> bash -c "$APP && python manage.py check_business_health" >> /home/amaury/logs/business_health.log 2>&1
```

Pense à garder une copie de l'ancienne crontab avant : `crontab -l > ~/crontab.backup`.

5. Vérifier sans attendre :

```bash
cd ~/Ovalpronos && source venv/bin/activate && python manage.py check_business_health
```

Résultat attendu : `Tout est en ordre.`, ou la liste des problèmes à traiter. Dans Healthchecks, chaque check passe au vert à sa première exécution.

**Bon à savoir** : si Healthchecks est en panne, les tâches tournent quand même. Seule l'alerte manque.

## 3. PostHog, alerte sur les erreurs du site (5 min)

Les erreurs 500 sont envoyées automatiquement dès que `POSTHOG_ENABLED=True` (déjà le cas en prod).

1. Dans PostHog, menu **Error tracking** : les erreurs y apparaissent, regroupées par type.
2. Créer une alerte email ([doc](https://posthog.com/docs/error-tracking/alerts)) :
   - créer une **Insight** de type *Trends* sur l'événement `$exception`, intervalle **heure** ;
   - sur cette insight, **Alerts** → **New alert** : condition "supérieur à 0", vérification **chaque heure**, notifier **ton email**.
3. Vérifier : l'insight s'affiche (même vide) et l'alerte est active.

PostHog ne sait pas envoyer d'email "à chaque nouvelle erreur", seulement vers Slack, Discord ou Teams. D'où cette alerte horaire.

## Quand une alerte arrive

| Alerte | Quoi faire |
|---|---|
| UptimeRobot "Down" | `sudo systemctl status gunicorn`, puis `sudo systemctl restart gunicorn`. Si une mise en ligne vient d'avoir lieu, voir `docs/ops/deploy.md` (Secours 1) |
| Healthchecks, tâche en échec | L'email contient la fin du message d'erreur. Le détail complet est dans `/home/amaury/logs/` |
| Healthchecks, tâche pas lancée | La crontab a été modifiée, ou le serveur était éteint : `crontab -l` |
| `business-health` : "Match joué mais jamais terminé" | Admin → Matchs : saisir le score, le statut "Terminé", puis l'action "Recalculer les points" |
| `business-health` : "pronos sans points" | Admin → Matchs : action "Recalculer les points" sur ce match |
| `business-health` : "sans cotes" | Admin → Matchs : saisir les 3 cotes (× 10), ou relancer `update_odds.yml` depuis GitHub Actions |
| `business-health` : "Disque rempli" | `du -sh ~/logs ~/backups /var/log` pour trouver ce qui grossit |
| PostHog, erreurs dans l'heure | Ouvrir Error tracking : le type d'erreur, la page et la ligne de code y sont |
