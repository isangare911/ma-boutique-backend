"""Tests de sécurité sur la synchronisation."""
import pytest
from inventory.models import Product


@pytest.mark.django_db
class TestSyncCrossTenant:

    def test_sync_cannot_overwrite_other_shop_product(self, client_a, product_b):
        """
        User A ne peut pas écraser un produit de la boutique B via sync.
        """
        payload = {
            'operations': [
                {
                    'operation_type': 'UPDATE',
                    'entity_type': 'PRODUCT',
                    'entity_id': product_b.id,   # ← produit de B
                    'payload': {
                        'name': 'Produit piraté',
                        'selling_price': '1',
                        'quantity': 999,
                    },
                }
            ]
        }

        response = client_a.post('/api/v1/sync/', payload, format='json')
        assert response.status_code == 200

        data = response.json()
        # L'opération doit avoir échoué
        assert data['summary']['failed'] == 1, (
            f"⚠️ Sync a réussi sur un produit d'une autre boutique : {data}"
        )

        # Le produit B n'a PAS été modifié
        product_b.refresh_from_db()
        assert product_b.name != 'Produit piraté'