import base64

from django.shortcuts import render
from rest_framework import permissions, views, viewsets
from rest_framework.decorators import link, api_view
from rest_framework.response import Response

import gevent

from models import *
from serializers import *

class PhotoDataViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PhotoData.objects.all()
    serializer_class = PhotoDataSerializer

    def create(self, request):
        photo_data = request.DATA.copy()
        for required in ('index', 'chunks', 'chunk', 'data'):
            if required not in photo_data:
                return Response({'result': 'error', 'errors': ['missing property "%s"' % required ]})

        try:
            photo_data['data'] = base64.b64decode(photo_data['data'])
        except:
            return Response({'result': 'error', 'errors': ['Invalid base64 photo_data']})

        photo = PhotoData.save_photo_chunk(**photo_data)
        complete = len(photo.url) > 0 if photo.url else False
        return Response(dict(result='ok', complete=complete))

    def latest(self, request, *args, **kwargs):
        status = PhotoStatus.get_status()
        response = {}

        if status.latest > -1:
            latest = PhotoData.objects.filter(index=status.latest).last()
            if latest:
                response.update(latest=latest.url)

        if status.next_progress > -1:
            response.update(next_progress=status.next_progress)

        return Response(response)

class LocationViewSet(viewsets.ModelViewSet):
    queryset = Location.objects.all()
    serializer_class = LocationSerializer
    paginate_by = 25

    def queryset_for_type(self, type):
        if type == 'balloon':
            return Location.objects.filter(type=Location.BALLOON)
        else:
            return Location.objects.filter(type=Location.CHASER, chaser__id=type)

    def create(self, request):
        data = request.DATA.copy()
        serializer = LocationSerializer(data=data)
        if serializer.is_valid():
            location = serializer.object
            if data.get('type') == 'C':
                location.chaser = request.user

            location.save()
            return Response({'result': 'ok'})
        else:
            return Response({'result': 'error', 'errors': serializer.errors})

    @link()
    def latest(self, request, *args, **kwargs):
        locations = []
        for result in Location.objects.values('type', 'chaser__id').distinct():
            query = Location.objects.filter(**result).order_by('-timestamp')
            locations.append(query.first())

        return Response(LocationSerializer(locations, many=True).data)

    @link()
    def by_type(self, request, *args, **kwargs):
        queryset = self.queryset_for_type(kwargs['type'])
        return Response(LocationSerializer(queryset, many=True).data)

class StatsViewSet(viewsets.ModelViewSet):
    queryset = Stats.objects.all()
    serializer_class = StatsSerializer

    def list(self, request):
        stats = Stats.get_stats()
        serializer = StatsSerializer(stats)
        return Response(serializer.data['data'])

    def create(self, request):
        data = request.DATA.copy()
        stats = Stats.get_stats()
        stats.data = data
        stats.save()
        return Response({'result': 'ok'})
