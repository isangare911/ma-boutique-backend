"""Tests de sécurité sur les crédits."""
import pytest
from django.utils import timezone
from datetime import timedelta


@pytest.mark.django_db
class TestCreditCrossTenant:

    def test_cannot_create_credit_for_other_shop_customer(
        self, client_a, customer_b
    ):
        """User A ne peut pas créer un crédit pour un client de la boutique B."""
        payload = {
            'customer': customer_b.id,   # ← client de la boutique B
            'total_amount': '5000',
            'due_date': (timezone.now() + timedelta(days=30)).isoformat(),
        }

        response = client_a.post('/api/v1/credits/', payload, format='json')

        assert response.status_code == 400, (
            f"⚠️ User A a pu créer un crédit pour un client de B "
            f"(status {response.status_code})"
        )


@pytest.mark.django_db
class TestCreditPayNoDoubleCounting:

    def test_paid_amount_is_not_doubled(
        self, client_b, credit_b, customer_b
    ):
        """
        Crédit 10000, paie 5000 → paid_amount == 5000 (pas 10000).
        """
        credit_b.refresh_from_db()
        assert float(credit_b.paid_amount) == 0.0

        response = client_b.post(
            f'/api/v1/credits/{credit_b.id}/pay/',
            {'amount': '5000', 'payment_method': 'Espèces'},
            format='json',
        )

        assert response.status_code == 200, response.json()

        credit_b.refresh_from_db()
        assert float(credit_b.paid_amount) == 5000.0, (
            f"⚠️ paid_amount = {credit_b.paid_amount} — attendu 5000, "
            "possible double comptage"
        )
        assert credit_b.status == 'ACTIVE', (
            f"⚠️ status = {credit_b.status} — devrait être ACTIVE (reste 5000)"
        )

    def test_paid_amount_full_then_paid_status(
        self, client_b, credit_b
    ):
        """Crédit 10000, paie 10000 → status == PAID."""
        response = client_b.post(
            f'/api/v1/credits/{credit_b.id}/pay/',
            {'amount': '10000', 'payment_method': 'Espèces'},
            format='json',
        )

        assert response.status_code == 200, response.json()

        credit_b.refresh_from_db()
        assert float(credit_b.paid_amount) == 10000.0
        assert credit_b.status == 'PAID'

    def test_cannot_pay_more_than_remaining(
        self, client_b, credit_b
    ):
        """Impossible de payer plus que le restant dû."""
        response = client_b.post(
            f'/api/v1/credits/{credit_b.id}/pay/',
            {'amount': '50000', 'payment_method': 'Espèces'},
            format='json',
        )

        assert response.status_code == 400


@pytest.mark.django_db
class TestCreditReadOnlyFields:

    def test_cannot_set_paid_amount_at_creation(self, client_b, customer_b):
        """Impossible de créer un crédit déjà 'payé'."""
        payload = {
            'customer': customer_b.id,
            'total_amount': '5000',
            'paid_amount': '5000',   # ← tentative
            'due_date': (timezone.now() + timedelta(days=30)).isoformat(),
        }

        response = client_b.post('/api/v1/credits/', payload, format='json')
        assert response.status_code == 201

        # Le paid_amount doit être 0, pas 5000
        assert float(response.json()['paid_amount']) == 0.0, (
            "⚠️ paid_amount est modifiable à la création — faille métier"
        )