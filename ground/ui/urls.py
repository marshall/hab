from django.conf.urls import patterns, include, url
from rest_framework.routers import DefaultRouter

from views import *

urlpatterns = patterns('ui.views',
    url(r'^$', index),
)
