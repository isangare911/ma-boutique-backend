"""Tests basiques : healthcheck + routes supprimées."""
import pytest


# ═══════════════════════════════════════════════════════════
# HEALTHCHECK
# ═══════════════════════════════════════════════════════════

def test_healthz_ok(anon_client):
    """Liveness — ne touche PAS la DB, toujours 200."""
    response = anon_client.get('/healthz/')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}


def test_readyz_ok(anon_client, db):
    """Readiness — vérifie la DB, 200 si tout va bien."""
    response = anon_client.get('/readyz/')
    assert response.status_code == 200
    assert response.json() == {'status': 'ready'}


# ═══════════════════════════════════════════════════════════
# ROUTES SUPPRIMÉES (failles fermées)
# ═══════════════════════════════════════════════════════════

def test_otp_routes_removed(anon_client):
    """Les routes OTP doivent renvoyer 404 (désactivées)."""
    response1 = anon_client.post('/api/v1/auth/request-otp/', {})
    response2 = anon_client.post('/api/v1/auth/verify-otp/', {})

    assert response1.status_code == 404, (
        "⚠️ /auth/request-otp/ est encore accessible — risque de login sans mot de passe"
    )
    assert response2.status_code == 404, (
        "⚠️ /auth/verify-otp/ est encore accessible — faille critique"
    )


def test_subscription_activate_removed(client_a):
    """La route d'activation d'abonnement direct doit être supprimée."""
    response = client_a.post(
        '/api/v1/subscription/activate/',
        {'plan': 'BUSINESS', 'duration_days': 3650},
        format='json',
    )
    assert response.status_code == 404, (
        "⚠️ /subscription/activate/ est encore accessible — "
        "n'importe qui peut s'octroyer un abonnement gratuit"
    )