"""Tests de sécurité sur l'authentification."""
import pytest


@pytest.mark.django_db
class TestRegisterSecurity:

    def test_register_weak_password_rejected(self, anon_client):
        """Un mot de passe trop court/faible doit être refusé."""
        response = anon_client.post(
            '/api/v1/auth/register/',
            {
                'phone': '+22370000999',
                'password': '123456',
                'shop_name': 'Test Shop',
            },
            format='json',
        )
        assert response.status_code == 400
        assert 'password' in response.json()

    def test_register_common_password_rejected(self, anon_client):
        """Un mot de passe courant doit être refusé."""
        response = anon_client.post(
            '/api/v1/auth/register/',
            {
                'phone': '+22370000998',
                'password': 'password',
                'shop_name': 'Test Shop',
            },
            format='json',
        )
        assert response.status_code == 400

    def test_register_duplicate_phone_rejected(self, anon_client, owner_a):
        """Un numéro déjà utilisé doit être refusé."""
        response = anon_client.post(
            '/api/v1/auth/register/',
            {
                'phone': owner_a.phone,
                'password': 'MotDePasse123!',
                'shop_name': 'Autre Shop',
            },
            format='json',
        )
        assert response.status_code == 400


@pytest.mark.django_db
class TestThrottling:

    def test_login_throttle(self, anon_client, owner_a):
        """6 tentatives de login d'affilée → 429 sur la 6e."""
        url = '/api/v1/auth/login/'
        payload = {
            'phone': owner_a.phone,
            'password': 'MauvaisMotDePasse',
        }

        statuses = []
        for _ in range(6):
            response = anon_client.post(url, payload, format='json')
            statuses.append(response.status_code)

        # Au moins une des dernières doit être 429
        assert 429 in statuses, (
            f"⚠️ Pas de throttling sur /auth/login/ — statuses: {statuses}"
        )

    def test_register_throttle(self, anon_client):
        """4 inscriptions d'affilée → 429 sur la 4e."""
        url = '/api/v1/auth/register/'

        statuses = []
        for i in range(4):
            response = anon_client.post(
                url,
                {
                    'phone': f'+2237000100{i}',
                    'password': 'MotDePasse123!',
                    'shop_name': f'Shop {i}',
                },
                format='json',
            )
            statuses.append(response.status_code)

        assert 429 in statuses, (
            f"⚠️ Pas de throttling sur /auth/register/ — statuses: {statuses}"
        )


@pytest.mark.django_db
class TestLogin:

    def test_login_success(self, anon_client, owner_a):
        """Login correct → tokens."""
        response = anon_client.post(
            '/api/v1/auth/login/',
            {'phone': owner_a.phone, 'password': 'MotDePasse123!'},
            format='json',
        )
        assert response.status_code == 200
        data = response.json()
        assert 'tokens' in data
        assert 'access' in data['tokens']

    def test_login_wrong_password(self, anon_client, owner_a):
        """Mauvais mot de passe → 400."""
        response = anon_client.post(
            '/api/v1/auth/login/',
            {'phone': owner_a.phone, 'password': 'Mauvais123!'},
            format='json',
        )
        assert response.status_code == 400


@pytest.mark.django_db
class TestJWT:

    def test_jwt_lifetime_is_short(self):
        """Le JWT doit expirer en 30 minutes max."""
        from django.conf import settings

        lifetime = settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME']
        assert lifetime.total_seconds() <= 1800, (
            f"⚠️ ACCESS_TOKEN_LIFETIME = {lifetime} — devrait être ≤ 30 min"
        )

    def test_blacklist_enabled(self):
        """BLACKLIST_AFTER_ROTATION doit être activé."""
        from django.conf import settings

        assert settings.SIMPLE_JWT['BLACKLIST_AFTER_ROTATION'] is True, (
            "⚠️ BLACKLIST_AFTER_ROTATION désactivé"
        )