from django.core.management.base import BaseCommand
from accounts.models import User, ShopUser


class Command(BaseCommand):
    help = 'Crée les entrées ShopUser manquantes pour les OWNER existants'

    def handle(self, *args, **options):
        owners_without_membership = User.objects.filter(
            role='OWNER',
            shop__isnull=False,
        ).exclude(
            shop_memberships__isnull=False,
        )

        count = 0
        for user in owners_without_membership:
            ShopUser.objects.create(
                shop=user.shop,
                user=user,
                role='OWNER',
            )
            count += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ ShopUser créé pour {user.phone} ({user.shop.name})'
                )
            )

        self.stdout.write(
            self.style.SUCCESS(f'\n{count} entrées ShopUser créées.')
        )