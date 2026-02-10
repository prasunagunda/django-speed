# speedapp/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("testfile/", views.testfile, name="testfile"),
    path("upload-test/", views.upload_test, name="upload_test"),
    path("ping/", views.ping, name="ping"),
    path("network/", views.network, name="network"),   # optional: your ISP lookup endpoint
]
