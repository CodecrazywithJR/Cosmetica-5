"""
Clinical signals for patient merge events.
"""
from django.dispatch import Signal

# Signal emitted after successful patient merge
# Payload (all values are UUIDs as strings, NO PHI):
#   - source_patient_id: UUID of merged patient
#   - target_patient_id: UUID of target patient
#   - strategy: Detection method (manual, phone_exact, email_exact, name_trgm, other)
#   - merged_by_user_id: UUID of user who performed merge (or None)
#   - merge_log_id: UUID of PatientMergeLog entry
patient_merged = Signal()


# Example listener (commented - for future integrations):
#
# from django.dispatch import receiver
# from django.db import transaction
# from apps.clinical.signals import patient_merged
#
# @receiver(patient_merged)
# def on_patient_merged(sender, source_patient_id, target_patient_id, 
#                        strategy, merged_by_user_id, merge_log_id, **kwargs):
#     """
#     Handle patient merge event.
#     
#     Use transaction.on_commit() to ensure actions only execute
#     if the merge transaction commits successfully.
#     """
#     def _send_notification():
#         # Example: Send notification to clinical ops
#         from apps.notifications.tasks import notify_patient_merge
#         notify_patient_merge.delay(
#             target_patient_id=target_patient_id,
#             merge_log_id=merge_log_id
#         )
#     
#     # Only execute after transaction commits
#     transaction.on_commit(_send_notification)

