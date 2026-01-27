#apps/accounts/signals.py

from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver

from apps.accounts.models import (
    User,
    Role,
    UserBranch,
    UserBranchRole,
    RoleCode,
)


# ---------------------------------------------------------------------
# USER LIFECYCLE SIGNALS
# ---------------------------------------------------------------------

@receiver(post_save, sender=User)
def user_post_create(sender, instance, created, **kwargs):
    """
    App-level initialization only.
    - NO permissions
    - NO audit logging
    - NO notifications
    """
    if not created:
        return

    # Example future-safe hook:
    # - profile creation
    # - default preferences
    pass


# ---------------------------------------------------------------------
# BRANCH ASSIGNMENT SAFETY
# ---------------------------------------------------------------------

@receiver(post_save, sender=UserBranch)
def ensure_single_primary_branch(sender, instance, created, **kwargs):
    """
    Ensure only ONE primary branch per user.
    """
    if not instance.is_primary:
        return

    (
        UserBranch.objects
        .filter(user=instance.user, is_primary=True)
        .exclude(pk=instance.pk)
        .update(is_primary=False)
    )


# ---------------------------------------------------------------------
# ROLE ASSIGNMENT SAFETY
# ---------------------------------------------------------------------

@receiver(post_save, sender=UserBranchRole)
def validate_branch_role(sender, instance, created, **kwargs):
    """
    Enforces consistency rules:
    - User must be assigned to branch before role assignment
    """
    if not instance.is_active:
        return

    exists = UserBranch.objects.filter(
        user=instance.user,
        branch=instance.branch,
        is_active=True
    ).exists()

    if not exists:
        raise ValueError(
            "User must be assigned to branch before assigning roles"
        )


# ---------------------------------------------------------------------
# CLEANUP ON USER DELETE (SOFT DELETE SAFE)
# ---------------------------------------------------------------------

@receiver(pre_delete, sender=User)
def cleanup_user_relations(sender, instance, **kwargs):
    """
    Defensive cleanup for hard deletes only.
    SoftDeleteMixin normally prevents this.
    """
    UserBranch.objects.filter(user=instance).delete()
    UserBranchRole.objects.filter(user=instance).delete()


# ---------------------------------------------------------------------
# ROLE DATA INTEGRITY
# ---------------------------------------------------------------------

@receiver(post_save, sender=Role)
def protect_system_roles(sender, instance, **kwargs):
    """
    Prevent accidental mutation of critical system roles.
    """
    protected = {
        RoleCode.ADMIN,
        RoleCode.MANAGER,
        RoleCode.DOCTOR,
        RoleCode.PATIENT,
    }

    if instance.code in protected and not instance.name:
        raise ValueError("System roles must have a name")
