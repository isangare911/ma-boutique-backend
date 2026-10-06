from rest_framework import serializers


class SyncOperationSerializer(serializers.Serializer):
    """Représente une opération à synchroniser (envoyée par Flutter)"""
    operation_type = serializers.ChoiceField(choices=['CREATE', 'UPDATE', 'DELETE'])
    entity_type = serializers.CharField(max_length=50)
    entity_id = serializers.CharField(max_length=100)
    payload = serializers.DictField()
    created_at = serializers.DateTimeField(required=False)


class SyncRequestSerializer(serializers.Serializer):
    """Requête globale de synchronisation"""
    # ⚡ max_length=200 pour éviter le DoS
    operations = SyncOperationSerializer(many=True, max_length=200)


class SyncResultSerializer(serializers.Serializer):
    """Résultat d'une opération de synchronisation"""
    entity_id = serializers.CharField()
    success = serializers.BooleanField()
    error = serializers.CharField(required=False, allow_blank=True)