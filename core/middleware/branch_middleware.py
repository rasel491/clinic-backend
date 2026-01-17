# core/middleware/branch_middleware.py

# from django.http import HttpResponseForbidden


# class BranchContextMiddleware:
#     """
#     Attaches active branch to request.
#     Rejects requests without valid branch context.
#     """

#     def __init__(self, get_response):
#         self.get_response = get_response

#     def __call__(self, request):
#         user = getattr(request, "user", None)

#         if user and user.is_authenticated:
#             branch_id = request.auth.get("branch_id") if request.auth else None

#             if not branch_id:
#                 return HttpResponseForbidden("Branch context missing")

#             request.branch_id = branch_id

#         return self.get_response(request)


# clinic/Backend/core/middleware/branch_middleware.py
class BranchMiddleware:
    """Middleware to set current branch in request for multi-branch support"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Add branch to request for easy access
        if hasattr(request, 'user') and not request.user.is_anonymous:
            # Set current branch from user's current_branch field
            request.branch = getattr(request.user, 'current_branch', None)
        else:
            request.branch = None
        
        return self.get_response(request)