from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

# Create a router and register our viewsets with it.
router = DefaultRouter()
router.register(r"messages", views.MessageView, basename="messages")

# The API URLs are now determined automatically by the router.
urlpatterns = [
    path("", include(router.urls)),
    path("conversation", views.ConversationView.as_view()),
    path("conversations", views.ConversationsInfoView.as_view()),
    path("conversations-download", views.ConversationsDownload.as_view()),
    path('votes/<int:pk>/', views.VoteCreateAPIView.as_view(), name='vote-create'),
    path('votes/', views.VoteCreateAPIView.as_view(), name='vote-create'),
    path('senders/', views.SenderAPIView.as_view(), name='vote-create'),
]
