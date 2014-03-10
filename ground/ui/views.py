import os

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.template import loader, Context

from ground import photos_dir

def index(request):
    tmpl = loader.get_template('index.html')
    return HttpResponse(tmpl.render(Context(dict(user=request.user))))

def photos(request, name=''):
    photo_file = os.path.abspath(os.path.join(photos_dir, name))
    if not os.path.exists(photo_file):
        return HttpResponse('File not found', status=404)

    if not photo_file.startswith(photos_dir):
        return HttpResponse('Invalid path', status=404)

    try:
        with open(photo_file, 'r') as f:
            return HttpResponse(f.read(), mimetype='image/jpeg')
    except IOError, e:
        return HttpResponse('Error opening: %s' % e, status=404)
