from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.utils import timezone
from django.db import transaction

from .serializers import SyncRequestSerializer
from .models import SyncLog
from accounts.permissions import CanUseSync, get_user_role


class SyncView(APIView):
    """
    POST /api/v1/sync/

    Reçoit un batch d'opérations et les traite.
    Réservé à OWNER, MANAGER.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        role = get_user_role(request.user)
        if role not in ('OWNER', 'MANAGER'):
            return Response(
                {'error': 'Accès refusé'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not request.user.shop:
            return Response(
                {
                    'error': 'Votre compte n\'est associé à aucune boutique. '
                             'Contactez le support.'
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = SyncRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        operations = serializer.validated_data['operations']
        results = []
        success_count = 0
        failed_count = 0

        for op in operations:
            try:
                with transaction.atomic():
                    self._process_operation(request.user, op)

                results.append({
                    'entity_id': op['entity_id'],
                    'success': True,
                })
                success_count += 1

                SyncLog.objects.create(
                    shop=request.user.shop,
                    user=request.user,
                    operation_type=op['operation_type'],
                    entity_type=op['entity_type'],
                    entity_id=op['entity_id'],
                    status='SUCCESS',
                )
            except Exception as e:
                results.append({
                    'entity_id': op['entity_id'],
                    'success': False,
                    'error': str(e),
                })
                failed_count += 1

                SyncLog.objects.create(
                    shop=request.user.shop,
                    user=request.user,
                    operation_type=op['operation_type'],
                    entity_type=op['entity_type'],
                    entity_id=op['entity_id'],
                    status='FAILED',
                    error_message=str(e),
                )

        return Response({
            'results': results,
            'summary': {
                'total': len(operations),
                'success': success_count,
                'failed': failed_count,
            },
        }, status=status.HTTP_200_OK)

    # ═══════════════════════════════════════════════════════════
    # HELPERS DE SÉCURITÉ
    # ═══════════════════════════════════════════════════════════

    def _check_no_conflict(self, model, entity_id, shop, entity_label):
        """
        Vérifie que l'entité n'appartient pas déjà à une autre boutique.
        """
        existing = model.objects.filter(id=entity_id).first()
        if existing and existing.shop_id != shop.id:
            raise Exception(
                f'Conflit : {entity_label} {entity_id} appartient à une autre boutique'
            )

    def _check_customer_belongs(self, shop, customer_id):
        """Vérifie qu'un customer_id appartient bien à la boutique."""
        if not customer_id:
            return None
        from customers.models import Customer
        customer = Customer.objects.filter(id=customer_id, shop=shop).first()
        if not customer:
            raise Exception(f'Client {customer_id} introuvable pour cette boutique')
        return customer

    def _check_product_belongs(self, shop, product_id):
        """Vérifie qu'un product_id appartient bien à la boutique."""
        if not product_id:
            return None
        from inventory.models import Product
        product = Product.objects.filter(id=product_id, shop=shop).first()
        if not product:
            raise Exception(f'Produit {product_id} introuvable pour cette boutique')
        return product

    # ═══════════════════════════════════════════════════════════
    # ROUTEUR
    # ═══════════════════════════════════════════════════════════

    def _process_operation(self, user, op):
        entity_type = op['entity_type']
        operation_type = op['operation_type']
        entity_id = op['entity_id']
        payload = op['payload']
        shop = user.shop

        if entity_type == 'SHOP_SETTINGS':
            self._handle_shop_settings(shop, operation_type, entity_id, payload)
            return

        handlers = {
            'PRODUCT': self._handle_product,
            'SALE': self._handle_sale,
            'CUSTOMER': self._handle_customer,
            'CREDIT': self._handle_credit,
            'CREDIT_PAYMENT': self._handle_credit_payment,
            'EXPENSE': self._handle_expense,
            'SUPPLIER': self._handle_supplier,
            'SUPPLIER_TRANSACTION': self._handle_supplier_transaction,
            'CASH_SESSION': self._handle_cash_session,
            'CASH_MOVEMENT': self._handle_cash_movement,
        }

        handler = handlers.get(entity_type)
        if not handler:
            raise Exception(f'Type d\'entité inconnu : {entity_type}')

        handler(shop, operation_type, entity_id, payload)

    # ═══════════════════════════════════════════════════════════
    # HANDLERS
    # ═══════════════════════════════════════════════════════════

    def _handle_product(self, shop, op_type, entity_id, payload):
        from inventory.models import Product

        if op_type == 'DELETE':
            Product.objects.filter(id=entity_id, shop=shop).delete()
            return

        self._check_no_conflict(Product, entity_id, shop, 'le produit')

        # ⚡ Clamp : ne jamais accepter une quantité négative
        allowed = {}
        for k, v in payload.items():
            if k == 'quantity':
                try:
                    v = max(0, int(v))
                except (TypeError, ValueError):
                    v = 0
            if k in ['name', 'reference', 'barcode', 'category',
                    'purchase_price', 'selling_price', 'quantity',
                    'alert_threshold', 'unit']:
                allowed[k] = v

        Product.objects.update_or_create(
            id=entity_id,
            defaults={'shop': shop, **allowed},
        )
    
    def _handle_customer(self, shop, op_type, entity_id, payload):
        from customers.models import Customer
        if op_type == 'DELETE':
            Customer.objects.filter(id=entity_id, shop=shop).delete()
            return

        self._check_no_conflict(Customer, entity_id, shop, 'le client')

        Customer.objects.update_or_create(
            id=entity_id,
            defaults={'shop': shop, **{
                k: v for k, v in payload.items()
                if k in ['name', 'phone', 'address']
            }},
        )

    def _handle_sale(self, shop, op_type, entity_id, payload):
        from sales.models import Sale, SaleItem
        from inventory.models import Product
        from django.db.models import F
        from decimal import Decimal

        # ═══════════════════════════════════════════════════════
        # DELETE
        # ═══════════════════════════════════════════════════════
        if op_type == 'DELETE':
            Sale.objects.filter(id=entity_id, shop=shop).delete()
            return

        # ═══════════════════════════════════════════════════════
        # UPDATE + CANCELLED → restaurer le stock
        # ═══════════════════════════════════════════════════════
        if op_type == 'UPDATE' and payload.get('status') == 'CANCELLED':
            sale = Sale.objects.filter(id=entity_id, shop=shop).first()
            if not sale:
                return
            if sale.status == 'CANCELLED':
                return

            items = payload.get('items') or []
            if items:
                for item in items:
                    product_id = item.get('product_id')
                    quantity = item.get('quantity', 0)
                    if product_id and quantity:
                        Product.objects.filter(
                            id=product_id, shop=shop
                        ).update(quantity=F('quantity') + quantity)
            else:
                for sale_item in sale.items.all():
                    if sale_item.product_id:
                        Product.objects.filter(
                            id=sale_item.product_id, shop=shop
                        ).update(quantity=F('quantity') + sale_item.quantity)

            sale.status = 'CANCELLED'
            sale.save(update_fields=['status'])
            return

        # ═══════════════════════════════════════════════════════
        # CREATE
        # ═══════════════════════════════════════════════════════
        if op_type == 'CREATE':
            self._check_no_conflict(Sale, entity_id, shop, 'la vente')

            customer = self._check_customer_belongs(
                shop, payload.get('customer_id')
            )

            # Calculer totals
            total_amount = Decimal('0')
            total_profit = Decimal('0')

            for item in payload.get('items', []):
                unit_price = Decimal(str(item.get('unit_price', 0) or 0))
                purchase_price = Decimal(
                    str(item.get('purchase_price', 0) or 0)
                )
                quantity = int(item.get('quantity', 0) or 0)

                total_amount += unit_price * quantity
                total_profit += (unit_price - purchase_price) * quantity

            sale, _ = Sale.objects.update_or_create(
                id=entity_id,
                defaults={
                    'shop': shop,
                    'customer': customer,
                    'total_amount': total_amount,
                    'total_profit': total_profit,
                    'payment_method': payload.get(
                        'payment_method', 'Espèces'
                    ),
                    'status': payload.get('status', 'COMPLETED'),
                },
            )

            for item in payload.get('items', []):
                product = self._check_product_belongs(
                    shop, item.get('product_id')
                )

                SaleItem.objects.update_or_create(
                    id=item['id'],
                    defaults={
                        'sale': sale,
                        'product': product,
                        'product_name': item['product_name'],
                        'unit_price': item['unit_price'],
                        'purchase_price': item.get('purchase_price', 0),
                        'quantity': item['quantity'],
                    },
                )

                # ⚡ Décrémenter le stock côté serveur
                if product and item.get('quantity', 0) > 0:
                    Product.objects.filter(
                        id=product.id, shop=shop
                    ).update(quantity=F('quantity') - item['quantity'])

    def _handle_credit(self, shop, op_type, entity_id, payload):
        from customers.models import Credit
        if op_type == 'DELETE':
            Credit.objects.filter(id=entity_id, shop=shop).delete()
            return

        self._check_no_conflict(Credit, entity_id, shop, 'le crédit')

        # ⚡ Vérifier que le customer appartient à la boutique
        customer = self._check_customer_belongs(shop, payload.get('customer_id'))
        if not customer:
            raise Exception('customer_id manquant pour le crédit')

        Credit.objects.update_or_create(
            id=entity_id,
            defaults={
                'shop': shop,
                'customer': customer,
                'total_amount': payload['total_amount'],
                'paid_amount': payload.get('paid_amount', 0),
                'due_date': payload['due_date'],
                'notes': payload.get('notes'),
            },
        )

    def _handle_credit_payment(self, shop, op_type, entity_id, payload):
        from customers.models import Credit, CreditPayment

        # ⚡ Vérifier que le crédit appartient bien à la boutique
        credit_id = payload.get('credit_id')
        if not credit_id:
            raise Exception('credit_id manquant')

        credit = Credit.objects.filter(id=credit_id, shop=shop).first()
        if not credit:
            raise Exception(f'Crédit {credit_id} introuvable pour cette boutique')

        if op_type == 'DELETE':
            CreditPayment.objects.filter(id=entity_id, credit=credit).delete()
            return

        CreditPayment.objects.update_or_create(
            id=entity_id,
            defaults={
                'credit': credit,
                'amount': payload['amount'],
                'payment_method': payload.get('payment_method', 'Espèces'),
                'payment_date': payload.get('date'),
            },
        )

    def _handle_expense(self, shop, op_type, entity_id, payload):
        from finance.models import Expense
        from django.utils.dateparse import parse_datetime
        from django.utils import timezone as django_timezone

        if op_type == 'DELETE':
            Expense.objects.filter(id=entity_id, shop=shop).delete()
            return

        self._check_no_conflict(Expense, entity_id, shop, 'la dépense')

        expense_date = payload.get('expense_date')
        if expense_date:
            parsed = parse_datetime(expense_date)
            if parsed and django_timezone.is_naive(parsed):
                parsed = django_timezone.make_aware(parsed)
                expense_date = parsed.isoformat()

        Expense.objects.update_or_create(
            id=entity_id,
            defaults={
                'shop': shop,
                'amount': payload['amount'],
                'category': payload['category'],
                'description': payload.get('description'),
                'expense_date': expense_date,
            },
        )

    def _handle_supplier(self, shop, op_type, entity_id, payload):
        from finance.models import Supplier
        if op_type == 'DELETE':
            Supplier.objects.filter(id=entity_id, shop=shop).delete()
            return

        self._check_no_conflict(Supplier, entity_id, shop, 'le fournisseur')

        Supplier.objects.update_or_create(
            id=entity_id,
            defaults={'shop': shop, **{
                k: v for k, v in payload.items()
                if k in ['name', 'phone', 'address', 'products_supplied', 'notes']
            }},
        )

    def _handle_supplier_transaction(self, shop, op_type, entity_id, payload):
        from finance.models import SupplierTransaction, Supplier

        if op_type == 'DELETE':
            SupplierTransaction.objects.filter(
                id=entity_id,
                supplier__shop=shop,
            ).delete()
            return

        supplier_id = payload.get('supplier_id')
        if not supplier_id:
            raise Exception('supplier_id manquant dans le payload')

        supplier = Supplier.objects.filter(id=supplier_id, shop=shop).first()
        if not supplier:
            raise Exception(f'Fournisseur {supplier_id} introuvable')

        SupplierTransaction.objects.update_or_create(
            id=entity_id,
            defaults={
                'supplier': supplier,
                'type': payload.get('type', 'PURCHASE'),
                'amount': payload.get('amount', 0),
                'description': payload.get('description'),
                'transaction_date': payload.get('transaction_date'),
            },
        )

    def _handle_cash_session(self, shop, op_type, entity_id, payload):
        from finance.models import CashSession
        from django.utils.dateparse import parse_datetime
        from django.utils import timezone as django_timezone

        if op_type == 'DELETE':
            CashSession.objects.filter(id=entity_id, shop=shop).delete()
            return

        self._check_no_conflict(CashSession, entity_id, shop, 'la session de caisse')

        opened_at = payload.get('opened_at')
        if opened_at:
            parsed = parse_datetime(opened_at)
            if parsed and django_timezone.is_naive(parsed):
                opened_at = django_timezone.make_aware(parsed).isoformat()

        closed_at = payload.get('closed_at')
        if closed_at:
            parsed = parse_datetime(closed_at)
            if parsed and django_timezone.is_naive(parsed):
                closed_at = django_timezone.make_aware(parsed).isoformat()

        defaults = {
            'shop': shop,
            'opening_balance': payload.get('opening_balance', 0),
            'status': payload.get('status', 'OPEN'),
        }

        if opened_at:
            defaults['opened_at'] = opened_at
        if payload.get('closing_balance') is not None:
            defaults['closing_balance'] = payload['closing_balance']
        if payload.get('theoretical_balance') is not None:
            defaults['theoretical_balance'] = payload['theoretical_balance']
        if payload.get('difference') is not None:
            defaults['difference'] = payload['difference']
        if closed_at:
            defaults['closed_at'] = closed_at

        CashSession.objects.update_or_create(id=entity_id, defaults=defaults)

    def _handle_cash_movement(self, shop, op_type, entity_id, payload):
        from finance.models import CashMovement, CashSession
        from django.utils.dateparse import parse_datetime
        from django.utils import timezone as django_timezone

        if op_type == 'DELETE':
            CashMovement.objects.filter(id=entity_id, session__shop=shop).delete()
            return

        session_id = payload.get('session_id')
        if not session_id:
            raise Exception('session_id manquant')

        session = CashSession.objects.filter(id=session_id, shop=shop).first()
        if not session:
            raise Exception(f'Session {session_id} introuvable')

        created_at = payload.get('created_at')
        if created_at:
            parsed = parse_datetime(created_at)
            if parsed and django_timezone.is_naive(parsed):
                created_at = django_timezone.make_aware(parsed)

        defaults = {
            'session': session,
            'type': payload.get('type', 'IN'),
            'amount': payload.get('amount', 0),
            'category': payload.get('category', 'Autre'),
            'description': payload.get('description'),
        }
        if created_at:
            defaults['created_at'] = created_at

        CashMovement.objects.update_or_create(id=entity_id, defaults=defaults)

    def _handle_shop_settings(self, shop, op_type, entity_id, payload):
        if not shop:
            raise Exception('Aucune boutique associée à l\'utilisateur connecté')

        allowed_fields = [
            'name', 'currency', 'address', 'phone',
            'email', 'owner_name', 'logo_path',
        ]

        changed = False
        for k in allowed_fields:
            if k in payload and payload[k] is not None:
                old_value = getattr(shop, k, None)
                new_value = payload[k]
                if old_value != new_value:
                    setattr(shop, k, new_value)
                    changed = True

        if changed:
            shop.save()


class SyncStatusView(APIView):
    """GET /api/v1/sync/status/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .models import SyncLog

        if not request.user.shop:
            return Response({
                'last_sync': None,
                'recent_logs': [],
            })

        logs = SyncLog.objects.filter(shop=request.user.shop)[:20]
        return Response({
            'last_sync': logs.first().created_at if logs.exists() else None,
            'recent_logs': [
                {
                    'entity_type': log.entity_type,
                    'entity_id': log.entity_id,
                    'status': log.status,
                    'created_at': log.created_at,
                }
                for log in logs
            ],
        })