"""URLs for core app."""
from django.urls import path

from core.views import (
    DashboardProgressView,
    HealthLiveView,
    HealthReadyView,
    ObjectiveDecomposeView,
    ObjectiveDetailView,
    ObjectiveGenerateTasksView,
    ObjectiveListCreateView,
    ObjectiveTaskCreateView,
    PerformanceSummaryView,
    PortfolioAssetCreateView,
    PortfolioProjectDetailView,
    PortfolioProjectListCreateView,
    TaskCompleteView,
    TaskCommentCreateView,
    TaskDetailView,
)

urlpatterns = [
    path("health/live/", HealthLiveView.as_view(), name="health-live"),
    path("health/ready/", HealthReadyView.as_view(), name="health-ready"),
    path("dashboard/progress/", DashboardProgressView.as_view(), name="dashboard-progress"),
    path("performance/summary/", PerformanceSummaryView.as_view(), name="performance-summary"),
    path("objectives/", ObjectiveListCreateView.as_view(), name="objectives"),
    path("objectives/<int:pk>/", ObjectiveDetailView.as_view(), name="objective-detail"),
    path("objectives/<int:id>/tasks/", ObjectiveTaskCreateView.as_view(), name="objective-tasks"),
    path("objectives/<int:id>/generate-tasks/", ObjectiveGenerateTasksView.as_view(), name="objective-generate-tasks"),
    path("objectives/<int:id>/decompose/", ObjectiveDecomposeView.as_view(), name="objective-decompose"),
    path("tasks/<int:pk>/", TaskDetailView.as_view(), name="task-detail"),
    path("tasks/<int:id>/complete/", TaskCompleteView.as_view(), name="task-complete"),
    path("tasks/<int:id>/comments/", TaskCommentCreateView.as_view(), name="task-comments"),
    path("portfolio/projects/", PortfolioProjectListCreateView.as_view(), name="portfolio-projects"),
    path("portfolio/projects/<int:pk>/", PortfolioProjectDetailView.as_view(), name="portfolio-project-detail"),
    path("portfolio/projects/<int:id>/assets/", PortfolioAssetCreateView.as_view(), name="portfolio-project-assets"),
]
