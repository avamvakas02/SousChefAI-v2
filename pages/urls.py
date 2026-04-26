from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing, name='landing'),
    path("pricing/", views.pricing, name="pricing"),
    path("about-us/", views.about_us, name="about_us"),
    path("contact-us/", views.contact_us, name="contact_us"),
    path("privacy/", views.privacy_policy, name="privacy_policy"),
]