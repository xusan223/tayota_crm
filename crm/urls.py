from django.contrib.auth import views as auth_views
from django.urls import path

from . import views


urlpatterns = [
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="crm/login.html"),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", views.dashboard, name="dashboard"),
    path("customers/<int:pk>/", views.customer_detail, name="customer-detail"),
    path("customers/<int:pk>/notes/", views.add_note, name="customer-add-note"),
    path("customers/<int:pk>/tasks/", views.add_task, name="customer-add-task"),
    path("deals/<int:pk>/stage/", views.change_deal_stage, name="deal-stage"),
    path("deals/<int:pk>/invoice/", views.create_invoice, name="deal-invoice"),
    path("documents/<int:pk>/", views.download_document, name="document-download"),
    path("tasks/<int:pk>/toggle/", views.toggle_task, name="task-toggle"),
    path("cars/", views.add_car, name="car-add"),
    path("cars/<int:pk>/", views.update_car, name="car-update"),
    path("export/excel/", views.export_excel, name="export-excel"),
]
