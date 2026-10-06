from django.http import JsonResponse
from django.db import connection


def healthz(request):
    """
    Liveness — je suis en vie.
    Ne touche PAS la DB. Toujours 200.
    Utilisé par Railway pour savoir si le conteneur doit être redémarré.
    """
    return JsonResponse({'status': 'ok'})


def readyz(request):
    """
    Readiness — je peux servir (DB OK).
    200 seulement si la DB répond, sinon 503.
    Utilisé pour surveiller la santé réelle de la plateforme.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        return JsonResponse({'status': 'ready'})
    except Exception as e:
        return JsonResponse(
            {'status': 'not_ready', 'detail': str(e)},
            status=503,
        )