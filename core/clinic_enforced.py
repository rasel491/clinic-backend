# from rest_framework import serializers
# from core.constants import UserRoles


# class ClinicEnforcedSerializer(serializers.ModelSerializer):
#     """
#     Enforces clinic assignment on create/update.
#     """

#     clinic_field = "clinic"

#     def validate(self, attrs):
#         user = self.context["request"].user

#         if user.role == UserRoles.SUPER_ADMIN:
#             return attrs

#         # Force clinic from request context
#         attrs[self.clinic_field] = self.context["request"].clinic
#         return attrs
