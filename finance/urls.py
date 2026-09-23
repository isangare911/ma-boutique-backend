from rest_framework.routers import DefaultRouter
from .views import CashSessionViewSet, ExpenseViewSet, SupplierViewSet

router = DefaultRouter()
router.register('cash-sessions', CashSessionViewSet, basename='cash-session')
router.register('expenses', ExpenseViewSet, basename='expense')
router.register('suppliers', SupplierViewSet, basename='supplier')

urlpatterns = router.urls