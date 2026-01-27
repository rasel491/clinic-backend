# # apps/audit/filters.py

# import django_filters
# from django.db.models import Q

# from apps.audit.models import AuditLog
# from apps.accounts.models import User
# from apps.clinics.models import Branch


# class AuditLogFilter(django_filters.FilterSet):
#     """
#     Advanced filtering for audit logs.
#     Used in admin + API.
#     """

#     branch = django_filters.ModelChoiceFilter(
#         queryset=Branch.objects.all()
#     )

#     user = django_filters.ModelChoiceFilter(
#         queryset=User.objects.all()
#     )

#     action = django_filters.CharFilter(
#         field_name="action",
#         lookup_expr="iexact"
#     )

#     model_name = django_filters.CharFilter(
#         field_name="model_name",
#         lookup_expr="iexact"
#     )

#     object_id = django_filters.CharFilter(
#         field_name="object_id",
#         lookup_expr="exact"
#     )

#     date_from = django_filters.DateTimeFilter(
#         field_name="timestamp",
#         lookup_expr="gte",
#         label="From date"
#     )

#     date_to = django_filters.DateTimeFilter(
#         field_name="timestamp",
#         lookup_expr="lte",
#         label="To date"
#     )

#     search = django_filters.CharFilter(method="filter_search")

#     class Meta:
#         model = AuditLog
#         fields = [
#             "branch",
#             "user",
#             "action",
#             "model_name",
#             "object_id",
#         ]

#     def filter_search(self, queryset, name, value):
#         """
#         Free-text search across important fields.
#         """
#         return queryset.filter(
#             Q(model_name__icontains=value)
#             | Q(object_id__icontains=value)
#             | Q(action__icontains=value)
#             | Q(user__email__icontains=value)
#             | Q(device_id__icontains=value)
#             | Q(ip_address__icontains=value)
#         )


# apps/audit/filters.py
import django_filters
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta

from apps.audit.models import AuditLog
from apps.accounts.models import User
from apps.clinics.models import Branch


class AuditLogFilter(django_filters.FilterSet):
    """
    Advanced filtering for audit logs.
    Used in admin + API.
    """

    # ==========================
    # CORE FILTERS
    # ==========================

    branch = django_filters.ModelChoiceFilter(
        queryset=Branch.objects.filter(is_active=True),
        help_text="Filter by active branch"
    )

    user = django_filters.ModelChoiceFilter(
        queryset=User.objects.filter(is_active=True),
        help_text="Filter by active user"
    )

    action = django_filters.CharFilter(
        field_name="action",
        lookup_expr="iexact"
    )

    model_name = django_filters.CharFilter(
        field_name="model_name",
        lookup_expr="iexact"
    )

    object_id = django_filters.CharFilter(
        field_name="object_id",
        lookup_expr="exact"
    )

    # ==========================
    # DATE RANGE FILTERS
    # ==========================

    date_from = django_filters.DateTimeFilter(
        field_name="timestamp",
        lookup_expr="gte",
        label="From datetime"
    )

    date_to = django_filters.DateTimeFilter(
        method="filter_date_to",
        label="To datetime (inclusive)"
    )

    # ==========================
    # HASH / FORENSIC FILTERS
    # ==========================

    record_hash = django_filters.CharFilter(
        field_name="record_hash",
        lookup_expr="exact",
        help_text="Exact audit record hash"
    )

    previous_hash = django_filters.CharFilter(
        field_name="previous_hash",
        lookup_expr="exact",
        help_text="Previous hash (chain verification)"
    )

    # ==========================
    # FULL TEXT SEARCH
    # ==========================

    search = django_filters.CharFilter(method="filter_search")

    class Meta:
        model = AuditLog
        fields = [
            "branch",
            "user",
            "action",
            "model_name",
            "object_id",
            "record_hash",
            "previous_hash",
        ]

    # ==========================
    # CUSTOM METHODS
    # ==========================

    def filter_search(self, queryset, name, value):
        """
        Free-text search across important audit fields.
        """
        return queryset.filter(
            Q(model_name__icontains=value)
            | Q(object_id__icontains=value)
            | Q(action__icontains=value)
            | Q(user__email__icontains=value)
            | Q(device_id__icontains=value)
            | Q(ip_address__icontains=value)
            | Q(record_hash__icontains=value)
        )

    def filter_date_to(self, queryset, name, value):
        """
        Make date_to inclusive till end of the day.
        """
        if not value:
            return queryset

        end_of_day = value + timedelta(days=1)
        return queryset.filter(timestamp__lt=end_of_day)

    @property
    def qs(self):
        """
        Enforce immutable audit ordering.
        """
        parent = super().qs
        return parent.order_by("id")
