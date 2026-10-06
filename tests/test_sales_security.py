"""Tests de sécurité sur les ventes."""
import pytest


@pytest.mark.django_db
class TestSaleTotalAmount:

    def test_total_amount_is_server_side(
        self, client_a, customer_a, product_a, owner_a
    ):
        """
        Même si le client envoie total_amount=0, le serveur doit recalculer.
        """
        payload = {
            'customer': customer_a.id,
            'total_amount': '0',          # ← tentative de fraude
            'total_profit': '0',          # ← tentative de fraude
            'payment_method': 'Espèces',
            'status': 'COMPLETED',
            'items': [
                {
                    'product': product_a.id,
                    'product_name': 'Riz 5kg',
                    'unit_price': '5000',
                    'purchase_price': '4000',
                    'quantity': 3,
                }
            ],
        }

        response = client_a.post('/api/v1/sales/', payload, format='json')
        assert response.status_code == 201, response.json()

        data = response.json()

        # total = 3 * 5000 = 15000
        assert float(data['total_amount']) == 15000.0, (
            f"⚠️ total_amount non recalculé : {data['total_amount']}"
        )
        # profit = 3 * (5000 - 4000) = 3000
        assert float(data['total_profit']) == 3000.0, (
            f"⚠️ total_profit non recalculé : {data['total_profit']}"
        )


@pytest.mark.django_db
class TestSalePatchForbidden:

    def test_patch_sale_returns_405(self, client_a, product_a, customer_a):
        """PATCH sur une vente → 405 (interdit)."""
        # Créer une vente
        payload = {
            'customer': customer_a.id,
            'payment_method': 'Espèces',
            'status': 'COMPLETED',
            'items': [
                {
                    'product': product_a.id,
                    'product_name': 'Riz 5kg',
                    'unit_price': '5000',
                    'purchase_price': '4000',
                    'quantity': 1,
                }
            ],
        }
        create_resp = client_a.post('/api/v1/sales/', payload, format='json')
        assert create_resp.status_code == 201

        sale_id = create_resp.json()['id']

        # Tenter un PATCH
        patch_resp = client_a.patch(
            f'/api/v1/sales/{sale_id}/',
            {'total_amount': '1'},
            format='json',
        )

        assert patch_resp.status_code == 405, (
            f"⚠️ PATCH sur une vente autorisé (status {patch_resp.status_code}) — "
            "un SELLER peut modifier le montant"
        )


@pytest.mark.django_db
class TestSaleCrossTenant:

    def test_cannot_use_product_of_other_shop(
        self, client_a, customer_a, product_b
    ):
        """User A ne peut pas vendre un produit de la boutique B."""
        payload = {
            'customer': customer_a.id,
            'payment_method': 'Espèces',
            'status': 'COMPLETED',
            'items': [
                {
                    'product': product_b.id,   # ← produit de la boutique B
                    'product_name': 'Huile 1L',
                    'unit_price': '1000',
                    'purchase_price': '800',
                    'quantity': 1,
                }
            ],
        }

        response = client_a.post('/api/v1/sales/', payload, format='json')

        assert response.status_code == 400, (
            f"⚠️ User A a pu vendre un produit de la boutique B "
            f"(status {response.status_code})"
        )