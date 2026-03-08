"""URLs for reviews app."""
from django.urls import path

from reviews.views import AdminReviewCreateView

urlpatterns = [
    path("reviews/", AdminReviewCreateView.as_view(), name="reviews"),
]
