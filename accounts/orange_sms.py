import base64
import logging
import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# RÉCUPÉRATION DU TOKEN ORANGE
# ═══════════════════════════════════════════════════════════

def _get_access_token():
    """
    Récupère un access token Orange, avec mise en cache.
    Le token est valide 1h — on le garde 50 minutes en cache.
    """
    cache_key = 'orange_access_token'
    token = cache.get(cache_key)
    if token:
        return token

    if not settings.ORANGE_CLIENT_ID or not settings.ORANGE_CLIENT_SECRET:
        raise ValueError(
            'Orange credentials manquants dans .env '
            '(ORANGE_CLIENT_ID / ORANGE_CLIENT_SECRET)'
        )

    # Auth Basic : client_id:client_secret en base64
    credentials = (
        f'{settings.ORANGE_CLIENT_ID}:{settings.ORANGE_CLIENT_SECRET}'
    )
    encoded = base64.b64encode(credentials.encode()).decode()

    headers = {
        'Authorization': f'Basic {encoded}',
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    data = {'grant_type': 'client_credentials'}

    try:
        response = requests.post(
            settings.ORANGE_OAUTH_URL,
            headers=headers,
            data=data,
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        token = payload.get('access_token')

        if not token:
            raise ValueError('Pas d\'access_token dans la réponse Orange')

        # Cache 50 minutes (le token Orange dure 1h)
        cache.set(cache_key, token, timeout=50 * 60)

        logger.info('✓ Orange: nouveau token obtenu')
        return token

    except requests.RequestException as e:
        logger.error(f'Orange token error: {e}')
        raise


# ═══════════════════════════════════════════════════════════
# ENVOI D'UN SMS
# ═══════════════════════════════════════════════════════════

def send_sms(phone, message):
    """
    Envoie un SMS via l'API Orange.

    Args:
        phone (str): numéro au format international, ex: +22378840999
        message (str): contenu du SMS (max ~160 caractères)

    Returns:
        dict: {'success': bool, 'message_id': str, 'error': str}
    """
    # Nettoyer le numéro (retirer espaces, tirets)
    phone = phone.replace(' ', '').replace('-', '')

    if not phone.startswith('+'):
        phone = '+' + phone

    try:
        token = _get_access_token()
    except Exception as e:
        return {
            'success': False,
            'error': f'Erreur token: {str(e)}',
        }

    # L'API Orange demande le sender sous forme URL-encodée
    from urllib.parse import quote
    sender = quote(settings.ORANGE_SENDER_NUMBER, safe='')

    url = f'{settings.ORANGE_SMS_URL}/{sender}/requests'

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }

    body = {
        'outboundSMSMessageRequest': {
            'address': f'tel:{phone}',
            'senderAddress': f'tel:{settings.ORANGE_SENDER_NUMBER}',
            'senderName': settings.ORANGE_SENDER_NAME,
            'outboundSMSTextMessage': {
                'message': message,
            },
        }
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json=body,
            timeout=20,
        )

        # 401 = token expiré → on le vide et on retente une fois
        if response.status_code == 401:
            cache.delete('orange_access_token')
            token = _get_access_token()
            headers['Authorization'] = f'Bearer {token}'
            response = requests.post(
                url,
                headers=headers,
                json=body,
                timeout=20,
            )

        if response.status_code in (200, 201):
            payload = response.json()
            resource = payload.get(
                'outboundSMSMessageRequest', {}
            ).get('resourceURL', '')
            logger.info(f'✓ SMS envoyé à {phone}')
            return {
                'success': True,
                'message_id': resource,
            }
        else:
            logger.error(
                f'Orange SMS error {response.status_code}: {response.text}'
            )
            return {
                'success': False,
                'error': f'HTTP {response.status_code}: {response.text[:200]}',
            }

    except requests.RequestException as e:
        logger.error(f'Orange SMS exception: {e}')
        return {
            'success': False,
            'error': f'Exception: {str(e)}',
        }