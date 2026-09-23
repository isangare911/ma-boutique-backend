from rest_framework.routers import DefaultRouter
from .views import CustomerViewSet, CreditViewSet

router = DefaultRouter()
router.register('customers', CustomerViewSet, basename='customer')
router.register('credits', CreditViewSet, basename='credit')

urlpatterns = router.urls