"""
Mobile UX regression tests for /predictions/ on Pixel 7 emulation.

Run with:
    pip install -r requirements-e2e.txt
    playwright install chromium
    pytest tests/e2e/ -v

These tests exercise the Zone C targeted HTMX swap introduced to fix the
keyboard/scroll UX on Chrome Android.
"""
from collections import Counter
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone

from apps.leagues.models import League
from apps.matches.models import Competition, Match, Team
from apps.predictions.models import Prediction

User = get_user_model()

# ── helpers ───────────────────────────────────────────────────────────────────


def _make_comp():
    return Competition.objects.create(
        name="E2E Comp", code="E2ETEST",
        external_id=-99001, season="2025",
        scoring_system="COTES", good_gap_pts=3, is_active=True,
    )


def _make_team(suffix):
    return Team.objects.create(
        external_id=-(hash(suffix) % 90000 + 60000),
        name=f"Team {suffix}", slug=f"e2e-{suffix}", country="France",
    )


def _make_match(comp, home, away, ext_id, dt_offset_days=7):
    return Match.objects.create(
        external_id=ext_id, competition=comp,
        home_team=home, away_team=away,
        datetime=timezone.now() + timedelta(days=dt_offset_days),
        status="SCHEDULED",
        cote_home=18, cote_draw=30, cote_away=22,
    )


def _login(page, live_server, user):
    """Inject a Django session cookie so Playwright is authenticated."""
    client = Client()
    client.force_login(user)
    session_id = client.cookies["sessionid"].value
    page.context.add_cookies([{
        "name": "sessionid",
        "value": session_id,
        "domain": "127.0.0.1",
        "path": "/",
    }])


def _duplicate_ids(page):
    """Return list of IDs that appear more than once in the current DOM."""
    ids = page.evaluate(
        "Array.from(document.querySelectorAll('[id]')).map(el => el.id)"
    )
    counts = Counter(ids)
    return [id_ for id_, n in counts.items() if n > 1]


# ── fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def prediction_setup(db):
    """Three open matches + one locked match, all in a single active league."""
    user = User.objects.create_user("e2e_user", "e2e@test.local", "pass")
    comp = _make_comp()
    league = League.objects.create(name="E2E League", creator=user)
    league.competitions.add(comp)
    league.members.add(user)

    home = _make_team("home")
    away = _make_team("away")

    matches = [
        _make_match(comp, home, away, ext_id=-(90001 + i), dt_offset_days=7 + i)
        for i in range(3)
    ]
    # Locked match: datetime in the past so is_locked returns True
    locked = _make_match(comp, home, away, ext_id=-90099, dt_offset_days=0)
    locked.datetime = timezone.now() - timedelta(hours=2)
    locked.save()

    return {"user": user, "matches": matches, "locked": locked}


# ── tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.django_db(transaction=True)
def test_three_predictions_no_scroll_no_focus_loss(page, live_server, prediction_setup):
    """
    Fill 3 cards in sequence:
    - scrollY must not move more than 2px after each Zone C swap
    - document.activeElement must be on the next card's home input after each save
    - input values must survive the swap intact
    - no duplicate IDs must appear in the DOM
    """
    user = prediction_setup["user"]
    matches = prediction_setup["matches"]

    _login(page, live_server, user)
    page.goto(f"{live_server.url}/predictions/")
    page.wait_for_selector('[id^="match-card-"]')

    for i, match in enumerate(matches):
        pk = match.pk
        next_match = matches[i + 1] if i < len(matches) - 1 else None

        score_h = page.locator(f"#score-h-{pk}")
        score_a = page.locator(f"#score-a-{pk}")

        scroll_before = page.evaluate("window.scrollY")

        # Tap + type home score (2 chars → JS auto-advances to score_a)
        score_h.tap()
        score_h.type("14", delay=50)

        # Type away score (2 chars → JS auto-advances to next card / blur)
        # The change event fires when focus leaves score_a, triggering HTMX
        score_a.type("22", delay=50)

        # Wait for Zone C to show the saved state (data-state attribute)
        page.wait_for_selector(f'#match-zone-c-{pk}[data-state="saved"]', timeout=5000)

        scroll_after = page.evaluate("window.scrollY")
        assert abs(scroll_after - scroll_before) <= 2, (
            f"Card {pk}: scroll jumped from {scroll_before} to {scroll_after}"
        )

        # Values must still be in the inputs (inputs were not replaced)
        assert score_h.input_value() == "14", f"Card {pk}: score_h lost its value"
        assert score_a.input_value() == "22", f"Card {pk}: score_a lost its value"

        # Active element must have moved to the next card's home input
        if next_match:
            active_id = page.evaluate("document.activeElement.id")
            assert active_id == f"score-h-{next_match.pk}", (
                f"Card {pk}: expected focus on score-h-{next_match.pk}, got {active_id!r}"
            )

        # No duplicate IDs anywhere in the DOM
        dupes = _duplicate_ids(page)
        assert not dupes, f"Duplicate IDs after save on card {pk}: {dupes}"


@pytest.mark.django_db(transaction=True)
def test_locked_match_triggers_full_card_replacement(page, live_server, prediction_setup):
    """
    When the server responds with HX-Retarget (locked race), HTMX replaces the
    entire card element — not just Zone C. Verify via a direct fetch that:
    - response status is 200
    - HX-Retarget header points at the card
    - HX-Reswap is outerHTML
    - body contains the locked card HTML
    """
    user = prediction_setup["user"]
    locked = prediction_setup["locked"]

    _login(page, live_server, user)
    # Navigate to get a valid CSRF token
    page.goto(f"{live_server.url}/predictions/")

    csrf = page.evaluate(
        "document.cookie.split(';').map(c=>c.trim())"
        ".find(c=>c.startsWith('csrftoken='))"
        "?.split('=')[1] || ''"
    )

    response = page.request.post(
        f"{live_server.url}/predictions/submit/{locked.pk}/",
        form={"score_h": "10", "score_a": "5"},
        headers={"X-CSRFToken": csrf},
    )

    assert response.status == 200
    assert response.headers.get("hx-retarget") == f"#match-card-{locked.pk}"
    assert response.headers.get("hx-reswap") == "outerHTML"
    assert f'id="match-card-{locked.pk}"' in response.text()
