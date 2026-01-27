# apps/accounts/models.py

from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    PermissionsMixin,
    BaseUserManager
)
from core.mixins.audit_fields import AuditFieldsMixin
from core.mixins.soft_delete import SoftDeleteMixin


class RoleCode:
    """Role constants - use these everywhere"""
    PATIENT = 'PATIENT'
    FRONT_DESK = 'FRONT_DESK'
    DOCTOR = 'DOCTOR'
    CASHIER = 'CASHIER'
    MANAGER = 'MANAGER'
    ADMIN = 'ADMIN'


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        
        user = self.create_user(email, password, **extra_fields)
        
        
        return user


class User(AbstractBaseUser, PermissionsMixin, AuditFieldsMixin, SoftDeleteMixin):
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, unique=True, blank=True, null=True)
    full_name = models.CharField(max_length=150)
    
    
    # Status
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    
    # Verification
    is_email_verified = models.BooleanField(default=False)
    is_phone_verified = models.BooleanField(default=False)
    
    # Security
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    failed_login_attempts = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    
    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["phone"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return self.email
    
    def active_roles(self, branch):
        return Role.objects.filter(
            branch_roles__user=self,
            branch_roles__branch=branch,
            branch_roles__is_active=True
        )
    
    def has_role(self, role_code, branch):
        return self.branch_roles.filter(
            role__code=role_code,
            branch=branch,
            is_active=True
        ).exists()
    
    def is_patient(self, branch):
        return self.has_role(RoleCode.PATIENT, branch)
    
    def is_doctor(self, branch):
        return self.has_role(RoleCode.DOCTOR, branch)
    
    def is_cashier(self, branch):
        return self.has_role(RoleCode.CASHIER, branch)
    
    def is_manager(self, branch):
        return self.has_role(RoleCode.MANAGER, branch) or self.has_role(RoleCode.ADMIN, branch)
    
    def is_admin(self, branch):
        return self.has_role(RoleCode.ADMIN, branch)


class Role(models.Model):
    """System roles - PATIENT, DOCTOR, etc."""
    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=50)

    role_config = models.JSONField(default=dict, blank=True)
    permissions = models.JSONField(default=list, blank=True)
    
    class Meta:
        ordering = ["code"]
    
    # constraints = [
    # models.UniqueConstraint(
    #     fields=["user"],
    #     condition=models.Q(is_primary=True),
    #     name="one_primary_branch_per_user"
    # )
    # ]

    def __str__(self):
        return f"{self.code} ({self.name})"


class UserRole(models.Model):
    """Global roles assigned to a user (non-branch specific)"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_roles")
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="user_roles")
    is_active = models.BooleanField(default=True)
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="assigned_roles_global")

    class Meta:
        unique_together = ("user", "role")

    def __str__(self):
        return f"{self.user.email} → {self.role.code}"

class UserBranch(models.Model):
    """Staff can work in multiple branches"""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="branches"
    )
    branch = models.ForeignKey(
        "clinics.Branch",
        on_delete=models.PROTECT,
        related_name="users"
    )
    
    is_active = models.BooleanField(default=True)
    is_primary = models.BooleanField(default=False)
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="branch_assignments"
    )

    class Meta:
        unique_together = ("user", "branch")
        indexes = [
            models.Index(fields=["user", "branch"]),
            models.Index(fields=["user", "is_active", "is_primary"]),
        ]

    def __str__(self):
        return f"{self.user.email} @ {self.branch.name}"

class UserBranchRole(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="branch_roles"
    )
    branch = models.ForeignKey(
        "clinics.Branch",
        on_delete=models.PROTECT,
        related_name="user_roles"
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name="branch_roles"
    )

    is_active = models.BooleanField(default=True)

    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="assigned_roles"
    )

    class Meta:
        unique_together = ("user", "branch", "role")
        indexes = [
            models.Index(fields=["user", "branch", "is_active"]),
            models.Index(fields=["branch", "role", "is_active"]),
        ]


    def __str__(self):
        return f"{self.user.email} → {self.role.code} @ {self.branch.name}"

class UserDevice(models.Model):
    """Track devices for security (prevent token theft)"""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="devices"
    )
    
    device_id = models.CharField(max_length=255)
    device_type = models.CharField(max_length=50)  # web / android / ios
    device_name = models.CharField(max_length=100, blank=True)
    user_agent = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    # Security
    refresh_token_hash = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    last_seen_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "device_id")
        ordering = ["-last_seen_at"]

        indexes = [
            models.Index(fields=["user", "device_id"]),
            models.Index(fields=["device_id"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.user.email} [{self.device_type}]"