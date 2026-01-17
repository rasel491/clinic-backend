# clinic/Backend/core/mixins/branch_querystd.py

from django.db import models

class BranchQuerysetMixin:
    """Mixin to automatically scope querysets by branch"""
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user if hasattr(self.request, 'user') else None
        
        if user and hasattr(user, 'branch') and user.branch:
            # If model has branch field
            if hasattr(self.get_queryset().model, 'branch'):
                return queryset.filter(branch=user.branch)
            # If model has clinic field
            elif hasattr(self.get_queryset().model, 'clinic'):
                return queryset.filter(clinic=user.branch)
        return queryset


class BranchScopedMixin(models.Model):
    """Mixin to add branch relationship to models"""
    branch = models.ForeignKey('clinics.Branch', on_delete=models.PROTECT)
    
    class Meta:
        abstract = True