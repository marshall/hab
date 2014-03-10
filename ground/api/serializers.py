from rest_framework import serializers

import logging

from models import *

class StatsSerializer(serializers.ModelSerializer):
    def transform_data(self, obj, value):
        return json.loads(value) if value else None

    class Meta:
        model = Stats
        fields = ('data',)

class PhotoDataSerializer(serializers.ModelSerializer):
    missing = serializers.Field(source='get_missing')

    class Meta:
        model = PhotoData
        fields = ('index', 'chunks', 'downloading', 'missing', 'url')

class LocationSerializer(serializers.ModelSerializer):
    chaser = serializers.SlugRelatedField(slug_field='username', read_only=True)

    class Meta:
        model = Location
        fields = ('type', 'chaser', 'altitude', 'latitude', 'longitude', 'timestamp')
        depth = 1
