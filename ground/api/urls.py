from django.conf.urls import patterns, include, url
from rest_framework.routers import DefaultRouter

from views import *

router = DefaultRouter()

photos = PhotoDataViewSet.as_view({
    'get': 'list',
    'post': 'create',
})

latest_photo = PhotoDataViewSet.as_view({
    'get': 'latest',
})

all_locations = LocationViewSet.as_view({
    'get': 'list',
    'post': 'create',
})

locations_by_type = LocationViewSet.as_view({
    'get': 'by_type'
})

latest_location = LocationViewSet.as_view({
    'get': 'latest'
})

stats = StatsViewSet.as_view({
    'get': 'list',
    'post': 'create',
})

urlpatterns = patterns('api.views',
    url(r'^', include(router.urls)),
    url(r'^locations/$', all_locations, name='all_locations'),
    url(r'^locations/(?P<type>balloon|[0-9]+)/$', locations_by_type, name='locations_by_type'),
    url(r'^locations/latest/$', latest_location, name='latest_location'),
    url(r'^photos/$', photos, name='photos'),
    url(r'^photos/latest/$', latest_photo, name='latest_photo'),
    url(r'^stats/$', stats, name='stats'),
)
