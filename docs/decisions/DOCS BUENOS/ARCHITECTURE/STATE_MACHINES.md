STATE MACHINES

Appointment

scheduled → confirmed
confirmed → checked_in
checked_in → completed
confirmed → cancelled
confirmed → no_show


Encounter

draft → finalized
draft → cancelled


Proposal

draft → sent
sent → accepted
draft → cancelled
sent → cancelled
sent → expired


TreatmentPlan

draft → active
active → completed
draft → cancelled