from datetime import timedelta
from django.utils import timezone
from .models import Shop


TRIAL_DAYS = 30
GRACE_PERIOD_DAYS = 7


class SubscriptionService:
    """Gère la logique d'abonnement."""

    @staticmethod
    def check_status(shop):
        """Vérifie et met à jour le statut de l'abonnement."""
        now = timezone.now()

        # Si pas de date de fin, c'est un essai en cours
        if shop.subscription_end is None:
            trial_end = shop.subscription_start + timedelta(days=TRIAL_DAYS)
            if now < trial_end:
                shop.subscription_status = 'TRIAL'
            else:
                # Essai terminé, on entre en période de grâce
                grace_end = trial_end + timedelta(days=GRACE_PERIOD_DAYS)
                if now < grace_end:
                    shop.subscription_status = 'GRACE_PERIOD'
                    shop.subscription_end = trial_end
                else:
                    shop.subscription_status = 'EXPIRED'
                    shop.subscription_end = trial_end
            shop.save()
            return shop.subscription_status

        # Abonnement payant
        if now < shop.subscription_end:
            shop.subscription_status = 'ACTIVE'
        else:
            # Vérifier la période de grâce
            grace_end = shop.subscription_end + timedelta(days=GRACE_PERIOD_DAYS)
            if now < grace_end:
                shop.subscription_status = 'GRACE_PERIOD'
            else:
                shop.subscription_status = 'EXPIRED'

        shop.save()
        return shop.subscription_status

    @staticmethod
    def is_active(shop):
        """Vrai si l'abonnement permet de vendre."""
        status = SubscriptionService.check_status(shop)
        return status in ['TRIAL', 'ACTIVE']

    @staticmethod
    def get_days_remaining(shop):
        """Retourne le nombre de jours restants."""
        now = timezone.now()
        if shop.subscription_end is None:
            trial_end = shop.subscription_start + timedelta(days=TRIAL_DAYS)
            delta = trial_end - now
        else:
            delta = shop.subscription_end - now
        return max(0, delta.days)

    @staticmethod
    def activate_plan(shop, plan, duration_days=30):
        """Active un abonnement payant."""
        now = timezone.now()
        shop.subscription_plan = plan
        shop.subscription_status = 'ACTIVE'
        shop.last_payment_date = now

        # Prolonger l'abonnement existant si encore actif
        if shop.subscription_end and shop.subscription_end > now:
            shop.subscription_end = shop.subscription_end + timedelta(days=duration_days)
        else:
            shop.subscription_end = now + timedelta(days=duration_days)

        shop.save()
        return shop