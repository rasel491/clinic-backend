# # clinic/Backend/core/middleware/branch_middleware.py
# class BranchMiddleware:
#     """Middleware to set current branch in request for multi-branch support"""
    
#     def __init__(self, get_response):
#         self.get_response = get_response
    
#     def __call__(self, request):
#         # Add branch to request for easy access
#         if hasattr(request, 'user') and not request.user.is_anonymous:
#             # Set current branch from user's current_branch field
#             request.branch = getattr(request.user, 'current_branch', None)
#         else:
#             request.branch = None
        
#         return self.get_response(request)

# core/middleware/branch_middleware.py

from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse

from apps.accounts.models import UserBranch, UserBranchRole


class BranchContextMiddleware(MiddlewareMixin):
    """
    Resolves branch context and user roles per request.

    Attaches:
    - request.branch
    - request.branch_roles
    - request.role_codes
    """

    BRANCH_HEADER = "HTTP_X_BRANCH_ID"

    def process_request(self, request):
        request.branch = None
        request.branch_roles = []
        request.role_codes = set()

        # Skip if unauthenticated
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return

        branch_id = request.META.get(self.BRANCH_HEADER)
        if not branch_id:
            return  # branch optional for some endpoints

        try:
            branch_id = int(branch_id)
        except (TypeError, ValueError):
            return JsonResponse(
                {"detail": "Invalid X-BRANCH-ID header"},
                status=400
            )

        # Verify user is assigned to this branch
        user_branch = (
            UserBranch.objects
            .select_related("branch")
            .filter(
                user=user,
                branch_id=branch_id,
                is_active=True
            )
            .first()
        )

        if not user_branch:
            return JsonResponse(
                {"detail": "User not assigned to this branch"},
                status=403
            )

        request.branch = user_branch.branch

        # Fetch active roles for this branch
        roles = (
            UserBranchRole.objects
            .select_related("role")
            .filter(
                user=user,
                branch=user_branch.branch,
                is_active=True
            )
        )

        request.branch_roles = roles
        request.role_codes = {r.role.code for r in roles}
