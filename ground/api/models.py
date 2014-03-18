import json
import logging
import os

from django.contrib.auth import get_user_model
from django.contrib.auth.models import User
from django.db.models import *
from django.db.models.signals import post_save
from django.dispatch import receiver
from rest_framework.authtoken.models import Token

from jsonfield import JSONField

from ground import photos_dir

@receiver(post_save, sender=get_user_model())
def create_auth_token(sender, instance=None, created=False, **kwargs):
    if created:
        Token.objects.create(user=instance)

class Stats(Model):
    data = JSONField()

    @classmethod
    def get_stats(cls):
        stats = cls.objects.first()
        if stats is None:
            stats = cls(data={})
            stats.save()

        return stats

class PhotoStatus(Model):
    latest = IntegerField(default=-1)
    next_progress = IntegerField(default=-1)

    @classmethod
    def get_status(cls):
        status = cls.objects.first()
        if not status:
            status = cls()

        return status

class PhotoData(Model):
    index = IntegerField()
    chunks = IntegerField()
    downloading = BooleanField(default=True)
    missing = JSONField()
    url = CharField(max_length=255, null=True, blank=True, default=None)

    @classmethod
    def save_photo_chunk(cls, index=0, chunks=0, **chunk):
        if not os.path.exists(photos_dir):
            os.makedirs(photos_dir)

        result = cls.objects.filter(index=index)
        photo = result[0] if len(result) > 0 else cls(index=index,
                                                      chunks=chunks,
                                                      missing=range(0, chunks))
        photo.chunks = chunks
        photo.save_chunk(**chunk)
        return photo

    def __init__(self, *args, **kwargs):
        super(PhotoData, self).__init__(*args, **kwargs)
        self.log = logging.getLogger('photo_data')

    def get_photo_dir(self):
        photo_dir = os.path.join(photos_dir, '%03d' % self.index)
        if not os.path.exists(photo_dir):
            os.makedirs(photo_dir)
        return photo_dir

    def get_chunk_file(self, chunk_index):
        return os.path.join(self.get_photo_dir(), '%03d.chunk' % chunk_index)

    def save_chunk(self, chunk=0, data=''):
        chunk_file = self.get_chunk_file(chunk)
        with open(chunk_file, 'w') as f:
            f.write(data)

        self.log.info('Saved photo %s chunk %s of %s to %s',
                      self.index, chunk, self.chunks, chunk_file)

        if chunk in self.missing:
            self.missing.remove(chunk)

        if len(self.missing) == 0:
            self.build_photo()

        self.save()

        status = PhotoStatus.get_status()
        if len(self.missing) == 0:
            status.latest = self.index

        status.next_progress = int(round(100 * ((float(self.chunks) - len(self.missing)) / self.chunks)))
        status.save()

    def build_photo(self):
        photo_path = os.path.join(photos_dir, '%03d.jpg' % self.index)
        with open(photo_path, 'w') as photo_file:
            for c in range(0, self.chunks):
                photo_file.write(open(self.get_chunk_file(c), 'r').read())

        self.downloading = False
        self.url = '/photos/%03d.jpg' % self.index

    def get_missing(self):
        return self.missing

    def to_json(self):
        return dict(index=self.index,
                    chunks=self.chunks,
                    downloading=self.downloading,
                    missing=self.missing,
                    url=self.url)

class Location(Model):
    BALLOON = 'B'
    CHASER  = 'C'
    TYPE_CHOICES = ((BALLOON, 'Balloon'),
                    (CHASER,  'Chaser'))

    type = CharField(max_length=1, choices=TYPE_CHOICES, default=BALLOON)
    chaser = ForeignKey(User, null=True, default=None)
    altitude = FloatField(default=0)
    latitude = FloatField(default=0)
    longitude = FloatField(default=0)
    timestamp = DateTimeField(auto_now_add=True)

    def __unicode__(self):
        return json.dumps(self.to_json())

    def to_json(self):
        return dict(timestamp=self.timestamp.isoformat(),
                    type=self.type,
                    chaser=self.chaser.username if self.chaser else None,
                    latitude=self.latitude,
                    longitude=self.longitude,
                    altitude=self.altitude)

