import uuid
from django.utils import timezone
from .models import Payment
from .subscription_service import SubscriptionService


class MobileMoneyService:
    """
    Service USSD manuel pour Mobile Money (Mali).
    
    Flux :
    1. Le client choisit un plan
    2. L'app affiche les instructions (numéro marchand, montant)
    3. Le client envoie l'argent via USSD
    4. Il reçoit un SMS avec un code de transaction
    5. Il entre le code dans l'app
    6. Le backend enregistre et active l'abonnement
    """

    # ═══════════════════════════════════════════════════════════
    # ⚡ NUMÉROS MARCHANDS — À REMPLACER PAR TES VRAIS NUMÉROS
    # ═══════════════════════════════════════════════════════════
    MERCHANT_NUMBERS = {
        'ORANGE_MONEY': '+223 70 00 00 01',   # ← Ton numéro Orange Money
        'WAVE': '+223 76 00 00 02',           # ← Ton numéro Wave
        'MOOV_MONEY': '+223 66 00 00 03',     # ← Ton numéro Moov Money
    }

    # ═══════════════════════════════════════════════════════════
    # CRÉER UN PAIEMENT
    # ═══════════════════════════════════════════════════════════
    @staticmethod
    def create_payment(shop, plan, method, payer_phone=None):
        """Crée une demande de paiement en attente."""
        amount = Payment.get_plan_price(plan)
        if amount == 0:
            raise ValueError(f'Plan invalide: {plan}')

        # ⚡ Annuler les anciens paiements en attente pour cette boutique
        Payment.objects.filter(
            shop=shop,
            status='PENDING',
        ).update(status='CANCELLED')

        payment = Payment.objects.create(
            shop=shop,
            plan=plan,
            amount=amount,
            method=method,
            status='PENDING',
            payer_phone=payer_phone,
            duration_days=30,
        )
        return payment

    # ═══════════════════════════════════════════════════════════
    # INSTRUCTIONS USSD
    # ═══════════════════════════════════════════════════════════
    @staticmethod
    def get_payment_instructions(payment):
        """Retourne les instructions détaillées pour le paiement USSD."""
        merchant_number = MobileMoneyService.MERCHANT_NUMBERS.get(
            payment.method, ''
        )
        amount = int(payment.amount)

        method_names = {
            'ORANGE_MONEY': 'Orange Money',
            'WAVE': 'Wave',
            'MOOV_MONEY': 'Moov Money',
        }

        # Instructions spécifiques par opérateur
        steps = {
            'ORANGE_MONEY': [
                'Composez #144# sur votre téléphone',
                'Choisissez "Transfert d\'argent"',
                f'Entrez le numéro : {merchant_number}',
                f'Entrez le montant : {amount} FCFA',
                'Validez avec votre code secret',
                'Vous recevrez un SMS avec un code de transaction',
            ],
            'WAVE': [
                'Ouvrez l\'application Wave',
                'Appuyez sur "Envoyer"',
                f'Entrez le numéro : {merchant_number}',
                f'Entrez le montant : {amount} FCFA',
                'Validez le paiement',
                'Vous recevrez une notification avec l\'ID de transaction',
            ],
            'MOOV_MONEY': [
                'Composez #155# sur votre téléphone',
                'Choisissez "Transfert"',
                f'Entrez le numéro : {merchant_number}',
                f'Entrez le montant : {amount} FCFA',
                'Validez avec votre code secret',
                'Vous recevrez un SMS avec un code de transaction',
            ],
        }

        return {
            'payment_id': payment.id,
            'amount': amount,
            'method': payment.method,
            'method_name': method_names.get(payment.method, payment.method),
            'merchant_number': merchant_number,
            'reference': payment.id,
            'steps': steps.get(payment.method, []),
            'warning': '⚠️ Conservez précieusement le code reçu par SMS.',
        }

    # ═══════════════════════════════════════════════════════════
    # CONFIRMER UN PAIEMENT
    # ═══════════════════════════════════════════════════════════
    @staticmethod
    def confirm_payment(payment_id, transaction_id, user):
        """Confirme un paiement et active l'abonnement."""
        try:
            payment = Payment.objects.get(
                id=payment_id,
                shop=user.shop,
            )
        except Payment.DoesNotExist:
            raise ValueError('Paiement introuvable')

        if payment.status == 'SUCCESS':
            raise ValueError('Ce paiement a déjà été confirmé')

        if payment.status == 'CANCELLED':
            raise ValueError('Ce paiement a été annulé')

        # ⚡ Enregistrer le code de transaction
        payment.transaction_id = transaction_id
        payment.status = 'SUCCESS'
        payment.paid_at = timezone.now()
        payment.save()

        # ⚡ Activer l'abonnement
        SubscriptionService.activate_plan(
            payment.shop,
            payment.plan,
            payment.duration_days,
        )

        return payment

    # ═══════════════════════════════════════════════════════════
    # ANNULER UN PAIEMENT
    # ═══════════════════════════════════════════════════════════
    @staticmethod
    def cancel_payment(payment_id, user):
        """Annule un paiement en attente."""
        try:
            payment = Payment.objects.get(
                id=payment_id,
                shop=user.shop,
            )
        except Payment.DoesNotExist:
            raise ValueError('Paiement introuvable')

        if payment.status == 'SUCCESS':
            raise ValueError('Impossible d\'annuler un paiement confirmé')

        payment.status = 'CANCELLED'
        payment.save()
        return payment

    # ═══════════════════════════════════════════════════════════
    # HISTORIQUE
    # ═══════════════════════════════════════════════════════════
    @staticmethod
    def get_shop_payments(shop, limit=20):
        """Retourne l'historique des paiements d'une boutique."""
        return Payment.objects.filter(shop=shop).order_by('-created_at')[:limit]