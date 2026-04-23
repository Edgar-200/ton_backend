from django.urls import path
from .views import (
    SendInvitationView,
    ReceivedInvitationsView,
    SentInvitationsView,
    RespondToInvitationView,
)

urlpatterns = [
    path('send/', SendInvitationView.as_view(), name='invitation-send'),
    path('received/', ReceivedInvitationsView.as_view(), name='invitation-received'),
    path('sent/', SentInvitationsView.as_view(), name='invitation-sent'),
    path('<uuid:invitation_id>/respond/', RespondToInvitationView.as_view(), name='invitation-respond'),
]
