# Actions manuelles

Ce que Claude ne peut pas faire depuis le repo : merges, serveur, comptes externes, DNS. Dans l'ordre. À cocher au fur et à mesure.

Mise à jour : 27 octobre 2026.

---

## Étape 1 : merger les PR, une par une

Après **chaque** merge, attendre la fin de la mise en ligne (onglet Actions de GitHub), puis **se connecter et se déconnecter** sur ovalpronos.com. Si quelque chose casse, s'arrêter et prévenir Claude.

Astuce : cocher "Delete branch" après chaque merge. Ça permet à GitHub de rebasculer automatiquement #9 vers `main`.

- [x] **#3** Sécurité de base (failles, cookies, HSTS). À merger en premier : elle ajoute la migration manquante sans laquelle la CI de #5 serait rouge.
- [x] **#2** L'API rugby n'écrit plus les scores. Effet à la sync de 7h suivante.
- [x] **#4** Bugs, contrôle des données Gemini, limites de tentatives.
- [x] **#5** Tests automatiques avant chaque mise en ligne. À partir de là, un push sur `main` ne part en prod que si les tests passent. Vérifier dans Actions : `CI` vert, puis `Deploy` qui se lance.
- [x] **#6** Script de mise en ligne avec retour automatique (voir étape 2).
- [x] **#7** Alertes (voir étape 3).
- [x] **Prévenir Claude** : il met à jour #8 et #9 (traductions en conflit avec #4).
- [x] **#8** Suppression de compte.
- [x] **#9** Pages légales et bandeau cookies (voir étape 4).
- [x] **#1** Rapport d'audit, quand tu veux.

## Étape 2 : après #6, brancher le nouveau script de mise en ligne (2 min)

Sur le serveur :

```bash
which pg_dump                          # doit afficher un chemin
cp ~/deploy.sh ~/deploy.sh.old
cat > ~/deploy.sh <<'EOF'
#!/bin/bash
exec /home/amaury/Ovalpronos/scripts/ops/deploy.sh "$@"
EOF
chmod +x ~/deploy.sh
~/deploy.sh                            # attendu : "Deploy complete: xxxxxxx -> xxxxxxx"
```

- [x] Fait. Détails et procédures de secours : `docs/ops/deploy.md`.

## Étape 3 : après #7, mettre en place les alertes (20 min)

Guide pas à pas : `docs/ops/monitoring.md`.

- [x] Compte **UptimeRobot** + 1 monitor sur `https://ovalpronos.com/rules/` (toutes les 5 min, alerte email)
- [x] Compte **Healthchecks.io** + 5 checks (`sync-matches`, `sync-live-scores`, `update-odds`, `deadline-reminders`, `business-health`)
- [x] Sur le serveur : `crontab -l > ~/crontab.backup`, puis `crontab -e` avec les nouvelles lignes du guide (adresses Healthchecks collées)
- [x] Tester : `python manage.py check_business_health` affiche "Tout est en ordre." ou la liste des problèmes
- [x] Dans **PostHog** : insight Trends sur `$exception` par heure, plus une alerte email "supérieur à 0"

## Étape 4 : après #9, conformité

- [ ] Faire relire si possible les 3 pages : `/legal/notice/`, `/legal/privacy/`, `/legal/terms/`
- [ ] Dans **PostHog** : vérifier que la durée de conservation des données est de **25 mois maximum** (annoncé dans la politique)
- [ ] Ouvrir le site en navigation privée : le bandeau apparaît, "Refuser" le fait disparaître, "Gérer les cookies" en bas de page le rouvre

## Étape 5 : à vérifier quand tu as un moment

- [x] SPF, DKIM et DMARC configurés dans le DNS Ionos pour l'envoi des emails
- [ ] Console Hetzner : l'option **Backups** est-elle activée sur le serveur ? (Les sauvegardes externes sont en pause. Aujourd'hui, seules des copies locales avant chaque migration existent, après #6.)
- [x] **RapidAPI** et **Google AI Studio** : vérifier que l'offre gratuite a une limite dure, sans facturation de dépassement

## Décisions encore ouvertes (pas urgentes)

| Sujet | Question |
|---|---|
| Comptes non vérifiés | Avec la vérification d'email : un compte non vérifié peut-il pronostiquer, apparaître au classement ? |
| Échec total des cotes | Simple alerte + saisie à la main (recommandé), ou bascule automatique en points fixes ? |
| 2FA admin | Double authentification pour ton compte admin ? (recommandé : oui) |
| Staging | Environnement de test sur le même serveur ? |

---

## Fait

| Date | Action |
|---|---|
| 2026-10-23 | GitHub connecté à Claude, app Claude autorisée sur le repo |
| 2026-10-23 | Infos serveur transmises (crontab, nginx, mémoire, disque, matchs masqués, deploy.sh, gunicorn) |
| 2026-10-27 | PR #1 à #9 mergées ; nouveau `deploy.sh` branché ; alertes UptimeRobot, Healthchecks et PostHog en place ; SPF/DKIM/DMARC configurés ; limites dures RapidAPI et Google AI Studio vérifiées |
