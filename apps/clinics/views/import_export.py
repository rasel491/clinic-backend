"""
Bulk import / export for Clinics app.
Handles CSV / Excel safely with validation and transactions.
"""

import csv
import io
from typing import List

from django.db import transaction
from django.http import HttpResponse
from django.utils.timezone import now

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser

from apps.clinics.models import Branch
from apps.clinics.serializers import BranchSerializer


def _read_csv(file) -> List[dict]:
    """
    Read CSV into list of dicts.
    Raises ValueError if malformed.
    """
    decoded = file.read().decode("utf-8")
    io_string = io.StringIO(decoded)
    reader = csv.DictReader(io_string)

    required_columns = {
        "name",
        "code",
        "address",
        "phone",
        "opening_time",
        "closing_time",
    }

    if not required_columns.issubset(reader.fieldnames):
        missing = required_columns - set(reader.fieldnames)
        raise ValueError(f"Missing columns: {', '.join(missing)}")

    return list(reader)


class BranchImportExportMixin:
    """
    Mixin used by BranchViewSet.
    """

    parser_classes = [MultiPartParser, FormParser]


    @action(detail=False, methods=["post"], url_path="import")
    def import_branches(self, request):
        """
        Import branches from CSV.
        """
        file = request.FILES.get("file")

        if not file:
            return Response(
                {"detail": "File is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            rows = _read_csv(file)
        except Exception as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        created, updated, errors = 0, 0, []

        with transaction.atomic():
            for index, row in enumerate(rows, start=2):
                try:
                    branch, is_created = Branch.objects.update_or_create(
                        code=row["code"].strip(),
                        defaults={
                            "name": row["name"].strip(),
                            "address": row["address"].strip(),
                            "phone": row["phone"].strip(),
                            "opening_time": row["opening_time"],
                            "closing_time": row["closing_time"],
                            "is_active": True,
                        },
                    )
                    created += int(is_created)
                    updated += int(not is_created)

                except Exception as exc:
                    errors.append(
                        {
                            "row": index,
                            "code": row.get("code"),
                            "error": str(exc),
                        }
                    )

        return Response(
            {
                "created": created,
                "updated": updated,
                "errors": errors,
            }
        )


    @action(detail=False, methods=["post"], url_path="export")
    def export_branches(self, request):
        """
        Export branches as CSV.
        """
        queryset = Branch.objects.filter(deleted_at__isnull=True)

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="branches_{now().date()}.csv"'
        )

        writer = csv.writer(response)
        writer.writerow([
            "name",
            "code",
            "address",
            "phone",
            "opening_time",
            "closing_time",
            "is_active",
        ])

        for branch in queryset.iterator():
            writer.writerow([
                branch.name,
                branch.code,
                branch.address,
                branch.phone,
                branch.opening_time,
                branch.closing_time,
                branch.is_active,
            ])

        return response


