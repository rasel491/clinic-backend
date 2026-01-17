# clinic/Backend/core/mixins/soft_delete.py

from django.db import models
from django.utils import timezone

class SoftDeleteMixin(models.Model):
    """Soft delete instead of actual deletion"""
    is_active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(null=True, blank=True, editable=False)
    deleted_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name='deleted_%(class)ss'
    )
    
    def delete(self, *args, **kwargs):
        """Override delete to soft delete"""
        from django.db import transaction
        
        with transaction.atomic():
            self.is_active = False
            self.deleted_at = timezone.now()
            if hasattr(self, '_request_user'):
                self.deleted_by = self._request_user
            self.save()
    
    class Meta:
        abstract = True