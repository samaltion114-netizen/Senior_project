"""URLs for core app."""
from django.urls import path

from core.views import (
    DashboardProgressView,
    HealthLiveView,
    HealthReadyView,
    ObjectiveDecomposeView,
    ObjectiveListCreateView,
    ObjectiveTaskCreateView,
    PerformanceSummaryView,
    PortfolioAssetCreateView,
    PortfolioProjectDetailView,
    PortfolioProjectListCreateView,
)

urlpatterns = [
    path("health/live/", HealthLiveView.as_view(), name="health-live"),
    path("health/ready/", HealthReadyView.as_view(), name="health-ready"),
    path("dashboard/progress/", DashboardProgressView.as_view(), name="dashboard-progress"),
    path("performance/summary/", PerformanceSummaryView.as_view(), name="performance-summary"),
    path("objectives/", ObjectiveListCreateView.as_view(), name="objectives"),
    path("objectives/<int:id>/tasks/", ObjectiveTaskCreateView.as_view(), name="objective-tasks"),
    path("objectives/<int:id>/decompose/", ObjectiveDecomposeView.as_view(), name="objective-decompose"),
    path("portfolio/projects/", PortfolioProjectListCreateView.as_view(), name="portfolio-projects"),
    path("portfolio/projects/<int:pk>/", PortfolioProjectDetailView.as_view(), name="portfolio-project-detail"),
    path("portfolio/projects/<int:id>/assets/", PortfolioAssetCreateView.as_view(), name="portfolio-project-assets"),
]
