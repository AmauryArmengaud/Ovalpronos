# Mise en ligne : fonctionnement et procédures de secours

Script : `scripts/ops/deploy.sh`, appelé par `~/deploy.sh` sur le serveur, lui-même lancé par GitHub (`deploy.yml`) quand les tests sont verts.

## Ce que fait le script, dans l'ordre

1. **Refuse de continuer** si un fichier suivi par git a été modifié à la main sur le serveur, pour ne rien écraser.
2. Récupère **la version exacte testée par GitHub** (ou la dernière de `main` si on le lance à la main).
3. Installe les bibliothèques.
4. Si la mise à jour modifie la structure de la base (migration), **copie la base** dans `~/backups/predeploy/`. Seules les 5 dernières copies sont gardées.
5. Applique les migrations, prépare les fichiers statiques, redémarre le site.
6. **Vérifie que le site répond** : `/rules/` (interroge la base) et `/accounts/login/` doivent répondre 200, avec jusqu'à 30 s d'attente pour le démarrage.
7. Si le site ne répond pas : **retour automatique à la version précédente**, puis croix rouge sur GitHub.

Si quelque chose plante avant le redémarrage (bibliothèque introuvable, migration en erreur), le code est remis à la version précédente. Le site n'a jamais cessé de tourner sur l'ancienne version.

Les migrations ne sont **jamais annulées automatiquement** : la copie de l'étape 4 sert à ça, à la main (voir plus bas).

## Installation (une seule fois)

À faire **après** le merge de la PR qui ajoute ce script, et **après** une première mise en ligne. L'ancien `~/deploy.sh` la fait encore et récupère ainsi le script sur le serveur.

```bash
# Vérifier que pg_dump est présent (installé avec PostgreSQL)
which pg_dump

# Remplacer ~/deploy.sh par un renvoi vers le script du repo
cp ~/deploy.sh ~/deploy.sh.old
cat > ~/deploy.sh <<'EOF'
#!/bin/bash
exec /home/amaury/Ovalpronos/scripts/ops/deploy.sh "$@"
EOF
chmod +x ~/deploy.sh

# Premier essai à la main (ne change rien si main est déjà à jour)
~/deploy.sh
```

Résultat attendu : `Deploy complete: xxxxxxx -> xxxxxxx`.

## Secours 1 : revenir à une version précédente du code

```bash
cd ~/Ovalpronos
git log --oneline -10                 # repérer la version voulue
git reset --keep <version>
source venv/bin/activate
pip install -r requirements.txt
python manage.py collectstatic --no-input
sudo systemctl restart gunicorn
```

La prochaine mise en ligne depuis GitHub repartira normalement.

## Secours 2 : remettre la base dans l'état d'avant une migration

⚠️ **Tout ce qui a été saisi depuis la copie est perdu** (pronos, inscriptions). À réserver au cas où une migration a abîmé des données.

```bash
cd ~/Ovalpronos && source venv/bin/activate
ls -lt ~/backups/predeploy/            # la plus récente en premier
DB_URL=$(python -c "from decouple import config; print(config('DATABASE_URL'))")
sudo systemctl stop gunicorn
pg_restore --clean --if-exists --no-owner --dbname="$DB_URL" ~/backups/predeploy/<fichier>.dump
# remettre aussi le code d'avant la migration (Secours 1), puis :
sudo systemctl start gunicorn
```

## Règle pour les migrations (expand / contract)

Le retour automatique remet l'ancien code **sans** annuler les migrations. L'ancien code doit donc toujours fonctionner avec la nouvelle structure de la base :

- **ajouter** une colonne : elle doit être nullable ou avoir une valeur par défaut ;
- **supprimer ou renommer** une colonne : en deux mises en ligne. D'abord le code arrête de l'utiliser, puis, dans une mise en ligne suivante, la migration la supprime.

## Ce que le script ne fait pas

- Ce n'est **pas une sauvegarde** : les copies restent sur le même serveur. Si le disque est perdu, elles le sont aussi.
- Il ne vérifie que 2 pages. Une page cassée ailleurs ne déclenchera pas de retour automatique.
