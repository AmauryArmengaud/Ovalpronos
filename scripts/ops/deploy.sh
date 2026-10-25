#!/usr/bin/env bash
# Production deploy with smoke test and automatic rollback.
# Usage: deploy.sh [<commit>]   (default: origin/main)
# Called by ~/deploy.sh (one-line wrapper) from the GitHub Actions deploy workflow.
set -Eeuo pipefail

APP_DIR=${APP_DIR:-/home/amaury/Ovalpronos}
SITE=${SITE:-https://ovalpronos.com}
DUMP_DIR=${DUMP_DIR:-/home/amaury/backups/predeploy}
KEEP_DUMPS=5
SMOKE_PATHS=(/rules/ /accounts/login/)

smoke_test() {
    # gunicorn needs a few seconds to boot after restart: retry for ~30s
    local path code
    for _ in $(seq 1 10); do
        local ok=1
        for path in "${SMOKE_PATHS[@]}"; do
            code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$SITE$path" || true)
            [ "$code" = 200 ] || { ok=0; break; }
        done
        [ "$ok" = 1 ] && return 0
        sleep 3
    done
    echo "Smoke test failed: $SITE$path answered $code"
    return 1
}

install_and_restart() {
    pip install --quiet -r requirements.txt
    python manage.py collectstatic --no-input --verbosity 0
    sudo systemctl restart gunicorn
}

# Everything runs inside main(): bash has then parsed the whole script before
# git rewrites this very file during the update
main() {
    cd "$APP_DIR"

    if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
        echo "Aborting: files were modified by hand on the server:"
        git status --short --untracked-files=no
        exit 1
    fi

    git fetch --quiet origin main
    local target=${1:-origin/main}
    local prev new
    prev=$(git rev-parse HEAD)
    git merge --ff-only --quiet "$target"
    new=$(git rev-parse HEAD)
    # any failure before the restart: put the code back, gunicorn still runs the old version
    # shellcheck disable=SC2064  # prev is expanded now on purpose
    trap "echo 'Deploy failed before restart, restoring ${prev:0:7}'; git reset --keep $prev; pip install --quiet -r requirements.txt" ERR

    # shellcheck disable=SC1091
    source venv/bin/activate
    pip install --quiet -r requirements.txt

    if ! python manage.py migrate --check >/dev/null 2>&1; then
        mkdir -p "$DUMP_DIR"
        local dump
        dump="$DUMP_DIR/$(date +%Y%m%d-%H%M%S)-before-${new:0:7}.dump"
        # same parsing as Django (python-decouple), handles quotes in .env
        pg_dump --format=custom --file="$dump" "$(python -c "from decouple import config; print(config('DATABASE_URL'))")"
        # shellcheck disable=SC2012  # dump names are ours: date + sha, no spaces
        ls -1t "$DUMP_DIR"/*.dump | tail -n +$((KEEP_DUMPS + 1)) | xargs -r rm --
        echo "Database copied before migrating: $dump"
    fi
    python manage.py migrate --no-input

    install_and_restart
    trap - ERR

    if smoke_test; then
        echo "Deploy complete: ${prev:0:7} -> ${new:0:7}"
        return 0
    fi

    # Migrations are not reversed automatically: expand/contract keeps the
    # previous code compatible with the new schema (see docs/ops/deploy.md)
    echo "Rolling back to ${prev:0:7}"
    git reset --keep "$prev"
    install_and_restart
    if smoke_test; then
        echo "Rollback OK: site is back on ${prev:0:7}. Deploy of ${new:0:7} FAILED."
    else
        echo "ROLLBACK FAILED: the site is down, manual action needed (docs/ops/deploy.md)"
    fi
    exit 1
}

main "$@"
