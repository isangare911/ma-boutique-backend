import uuid
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum, Count, Q
from datetime import timedelta
from .models import Payment, Shop
from .subscription_service import SubscriptionService


class MobileMoneyService:
    """Service USSD avec codes uniques pour Mobile Money (Mali)."""

    MERCHANT_NUMBERS = {
        'ORANGE_MONEY': '+223 84 09 99 44',
        'WAVE': '+223 84 09 99 44',
        'MOOV_MONEY': '+223 63 54 32 54',
    }

    # ═══════════════════════════════════════════════════════════
    # CRÉER UN PAIEMENT
    # ═══════════════════════════════════════════════════════════
    @staticmethod
    @transaction.atomic
    def create_payment(shop, plan, method, payer_phone=None):
        amount = Payment.get_plan_price(plan)
        if amount == 0:
            raise ValueError(f'Plan invalide: {plan}')

        # Annuler les anciens paiements en attente
        Payment.objects.filter(
            shop=shop,
            status__in=['PENDING', 'PENDING_REVIEW'],
        ).update(status='CANCELLED')

        payment = Payment(
            shop=shop,
            plan=plan,
            amount=amount,
            method=method,
            status='PENDING',
            payer_phone=payer_phone,
            duration_days=30,
        )
        payment.save()

        return payment

    # ═══════════════════════════════════════════════════════════
    # INSTRUCTIONS
    # ═══════════════════════════════════════════════════════════
    @staticmethod
    def get_payment_instructions(payment):
        merchant_number = MobileMoneyService.MERCHANT_NUMBERS.get(
            payment.method, ''
        )
        amount = int(payment.amount)
        code = payment.payment_code or '—'

        method_names = {
            'ORANGE_MONEY': 'Orange Money',
            'WAVE': 'Wave',
            'MOOV_MONEY': 'Moov Money',
        }

        steps = {
            'ORANGE_MONEY': [
                'Composez #144# sur votre téléphone',
                'Choisissez "Transfert d\'argent"',
                f'Entrez le numéro : {merchant_number}',
                f'Entrez le montant : {amount} FCFA',
                f'⚠️ Dans "Motif", entrez : {code}',
                'Validez avec votre code secret',
                'Vous recevrez un SMS de confirmation',
            ],
            'WAVE': [
                'Ouvrez l\'application Wave',
                'Appuyez sur "Envoyer"',
                f'Entrez le numéro : {merchant_number}',
                f'Entrez le montant : {amount} FCFA',
                f'⚠️ Dans "Motif", entrez : {code}',
                'Validez le paiement',
                'Vous recevrez une notification',
            ],
            'MOOV_MONEY': [
                'Composez #155# sur votre téléphone',
                'Choisissez "Transfert"',
                f'Entrez le numéro : {merchant_number}',
                f'Entrez le montant : {amount} FCFA',
                f'⚠️ Dans "Motif", entrez : {code}',
                'Validez avec votre code secret',
                'Vous recevrez un SMS de confirmation',
            ],
        }

        return {
            'payment_id': payment.id,
            'payment_code': code,
            'amount': amount,
            'method': payment.method,
            'method_name': method_names.get(payment.method, payment.method),
            'merchant_number': merchant_number,
            'reference': code,
            'steps': steps.get(payment.method, []),
            'warning': f'⚠️ IMPORTANT : Mentionnez le code {code} dans la référence du transfert.',
            'expires_in_minutes': 60,
        }

    # ═══════════════════════════════════════════════════════════
    # SOUMETTRE LA PREUVE
    # ═══════════════════════════════════════════════════════════
    @staticmethod
    @transaction.atomic
    def submit_payment_proof(payment_id, transaction_id, user):
        try:
            payment = Payment.objects.select_for_update().get(
                id=payment_id,
                shop=user.shop,
            )
        except Payment.DoesNotExist:
            raise ValueError('Paiement introuvable')

        if payment.status != 'PENDING':
            raise ValueError('Ce paiement a déjà été traité')

        transaction_id = (transaction_id or '').strip()

        # ⚡ Validation minimale : non-vide + longueur raisonnable.
        # L'admin validera manuellement en vérifiant ses SMS Orange Money.
        if not transaction_id:
            raise ValueError('Code de transaction requis')

        if len(transaction_id) < 4:
            raise ValueError(
                'Code de transaction trop court (minimum 4 caractères)'
            )

        if len(transaction_id) > 200:
            raise ValueError(
                'Code de transaction trop long (maximum 200 caractères)'
            )

        # ⚡ Unicité : le code ne doit pas être utilisé ailleurs
        existing = Payment.objects.filter(
            transaction_id=transaction_id,
        ).exclude(id=payment.id).first()

        if existing:
            raise ValueError('Ce code de transaction a déjà été utilisé')

        payment.transaction_id = transaction_id
        payment.status = 'PENDING_REVIEW'
        payment.save()

        return payment

    # ═══════════════════════════════════════════════════════════
    # APPROUVER / REJETER (Admin uniquement)
    # ═══════════════════════════════════════════════════════════
    @staticmethod
    @transaction.atomic
    def approve_payment(payment_id, admin_user):
        try:
            payment = Payment.objects.select_for_update().get(id=payment_id)
        except Payment.DoesNotExist:
            raise ValueError('Paiement introuvable')

        if payment.status == 'APPROVED':
            raise ValueError('Paiement déjà approuvé')

        if payment.status != 'PENDING_REVIEW':
            raise ValueError('Ce paiement n\'est pas en attente de validation')

        payment.status = 'APPROVED'
        payment.approved_by = admin_user
        payment.approved_at = timezone.now()
        payment.save()

        SubscriptionService.activate_plan(
            payment.shop,
            payment.plan,
            payment.duration_days,
        )

        return payment

    @staticmethod
    @transaction.atomic
    def reject_payment(payment_id, reason, admin_user):
        try:
            payment = Payment.objects.select_for_update().get(id=payment_id)
        except Payment.DoesNotExist:
            raise ValueError('Paiement introuvable')

        if payment.status == 'APPROVED':
            raise ValueError('Impossible de rejeter un paiement approuvé')

        payment.status = 'REJECTED'
        payment.rejection_reason = reason
        payment.approved_by = admin_user
        payment.approved_at = timezone.now()
        payment.save()

        return payment

    @staticmethod
    @transaction.atomic
    def cancel_payment(payment_id, user):
        try:
            payment = Payment.objects.select_for_update().get(
                id=payment_id, shop=user.shop
            )
        except Payment.DoesNotExist:
            raise ValueError('Paiement introuvable')

        if payment.status == 'APPROVED':
            raise ValueError('Impossible d\'annuler un paiement approuvé')

        payment.status = 'CANCELLED'
        payment.save()
        return payment

    # ═══════════════════════════════════════════════════════════
    # STATISTIQUES ADMIN
    # ═══════════════════════════════════════════════════════════
    @staticmethod
    def get_admin_stats():
        now = timezone.now()
        start_of_month = now.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        start_of_week = now - timedelta(days=7)

        total_revenue = Payment.objects.filter(
            status='APPROVED'
        ).aggregate(total=Sum('amount'))['total'] or 0

        monthly_revenue = Payment.objects.filter(
            status='APPROVED',
            approved_at__gte=start_of_month,
        ).aggregate(total=Sum('amount'))['total'] or 0

        weekly_revenue = Payment.objects.filter(
            status='APPROVED',
            approved_at__gte=start_of_week,
        ).aggregate(total=Sum('amount'))['total'] or 0

        total_payments = Payment.objects.filter(status='APPROVED').count()
        pending_review = Payment.objects.filter(status='PENDING_REVIEW').count()
        rejected_payments = Payment.objects.filter(status='REJECTED').count()

        total_shops = Shop.objects.count()
        active_shops = Shop.objects.filter(subscription_status='ACTIVE').count()
        trial_shops = Shop.objects.filter(subscription_status='TRIAL').count()
        grace_shops = Shop.objects.filter(subscription_status='GRACE_PERIOD').count()
        expired_shops = Shop.objects.filter(subscription_status='EXPIRED').count()

        new_shops_this_month = Shop.objects.filter(
            created_at__gte=start_of_month
        ).count()

        new_shops_this_week = Shop.objects.filter(
            created_at__gte=start_of_week
        ).count()

        revenue_by_plan = list(
            Payment.objects.filter(status='APPROVED')
            .values('plan')
            .annotate(total=Sum('amount'), count=Count('id'))
            .order_by('-total')
        )
        for item in revenue_by_plan:
            item['total'] = float(item['total'] or 0)

        revenue_by_method = list(
            Payment.objects.filter(status='APPROVED')
            .values('method')
            .annotate(total=Sum('amount'), count=Count('id'))
            .order_by('-total')
        )
        for item in revenue_by_method:
            item['total'] = float(item['total'] or 0)

        renewal_count = Shop.objects.annotate(
            payment_count=Count(
                'payments',
                filter=Q(payments__status='APPROVED'),
            )
        ).filter(payment_count__gte=2).count()

        renewal_rate = (
            (renewal_count / active_shops * 100) if active_shops > 0 else 0
        )

        mrr = float(monthly_revenue)

        return {
            'total_revenue': float(total_revenue),
            'monthly_revenue': float(monthly_revenue),
            'weekly_revenue': float(weekly_revenue),
            'mrr': mrr,
            'total_payments': total_payments,
            'pending_review': pending_review,
            'rejected_payments': rejected_payments,
            'total_shops': total_shops,
            'active_shops': active_shops,
            'trial_shops': trial_shops,
            'grace_shops': grace_shops,
            'expired_shops': expired_shops,
            'new_shops_this_month': new_shops_this_month,
            'new_shops_this_week': new_shops_this_week,
            'renewal_rate': round(renewal_rate, 1),
            'revenue_by_plan': revenue_by_plan,
            'revenue_by_method': revenue_by_method,
        }

    @staticmethod
    def get_all_shops_with_stats():
        shops = Shop.objects.all().order_by('-created_at')

        result = []
        for shop in shops:
            approved_payments = shop.payments.filter(status='APPROVED').count()

            total_paid = shop.payments.filter(
                status='APPROVED'
            ).aggregate(total=Sum('amount'))['total'] or 0

            last_payment = shop.payments.filter(
                status='APPROVED'
            ).order_by('-approved_at').first()

            days_remaining = 0
            if shop.subscription_end:
                delta = shop.subscription_end - timezone.now()
                days_remaining = max(0, delta.days)
            elif shop.subscription_status == 'TRIAL':
                trial_end = shop.subscription_start + timedelta(days=30)
                delta = trial_end - timezone.now()
                days_remaining = max(0, delta.days)

            result.append({
                'id': shop.id,
                'name': shop.name,
                'owner_name': shop.owner_name or '—',
                'phone': shop.phone or '—',
                'currency': shop.currency,
                'plan': shop.subscription_plan,
                'status': shop.subscription_status,
                'days_remaining': days_remaining,
                'start_date': shop.subscription_start,
                'end_date': shop.subscription_end,
                'is_active': shop.is_active,
                'created_at': shop.created_at,
                'total_paid': float(total_paid),
                'payment_count': approved_payments,
                'last_payment_date': (
                    last_payment.approved_at if last_payment else None
                ),
            })

        return result

    @staticmethod
    def get_all_payments(status_filter=None, limit=100):
        payments = Payment.objects.select_related('shop').all()

        if status_filter:
            payments = payments.filter(status=status_filter)

        return payments.order_by('-created_at')[:limit]

    @staticmethod
    def get_shop_payments(shop, limit=20):
        return Payment.objects.filter(shop=shop).order_by('-created_at')[:limit]