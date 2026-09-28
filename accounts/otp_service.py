import random
import logging
from django.conf import settings
from django.core.cache import cache
from .orange_sms import send_sms

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# GÉNÉRATION DU CODE
# ═══════════════════════════════════════════════════════════

def generate_otp():
    """Génère un code à 6 chiffres."""
    return str(random.randint(100000, 999999))


def _cache_key(phone):
    """Clé unique pour stocker l'OTP dans le cache."""
    return f'otp:{phone}'


def _rate_limit_key(phone):
    """Clé pour limiter le nombre de demandes."""
    return f'otp_ratelimit:{phone}'


# ═══════════════════════════════════════════════════════════
# ENVOI DE L'OTP
# ═══════════════════════════════════════════════════════════

def request_otp(phone):
    """
    Génère un OTP, l'envoie par SMS, et le stocke en cache.

    Rate limit : max 3 demandes par 10 minutes par numéro.

    Returns:
        dict: {'success': bool, 'error': str}
    """
    phone = phone.replace(' ', '').replace('-', '')

    # Rate limiting simple
    rl_key = _rate_limit_key(phone)
    attempts = cache.get(rl_key, 0)
    if attempts >= 3:
        return {
            'success': False,
            'error': 'Trop de tentatives. Réessayez dans 10 minutes.',
        }
    cache.set(rl_key, attempts + 1, timeout=10 * 60)

    # Générer le code
    code = generate_otp()

    # Envoyer le SMS
    message = (
        f'Votre code Ma Boutique: {code}\n'
        f'Valable {settings.OTP_EXPIRY_SECONDS // 60} minutes.'
    )
    result = send_sms(phone, message)

    if not result.get('success'):
        logger.error(f'Échec envoi OTP à {phone}: {result.get("error")}')
        return {
            'success': False,
            'error': 'Impossible d\'envoyer le SMS. Réessayez.',
        }

    # Stocker le code (valide 5 minutes par défaut)
    cache.set(_cache_key(phone), code, timeout=settings.OTP_EXPIRY_SECONDS)

    logger.info(f'✓ OTP envoyé à {phone}')
    return {'success': True}


# ═══════════════════════════════════════════════════════════
# VÉRIFICATION DE L'OTP
# ═══════════════════════════════════════════════════════════

def verify_otp(phone, code):
    """
    Vérifie que le code correspond à celui stocké en cache.

    Returns:
        bool: True si valide
    """
    phone = phone.replace(' ', '').replace('-', '')
    stored = cache.get(_cache_key(phone))

    if not stored:
        return False

    if stored != code:
        return False

    # Code correct → on le supprime (usage unique)
    cache.delete(_cache_key(phone))
    return True