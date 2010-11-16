import os
from django.conf.urls.defaults import *
import views
urlpatterns = patterns('',
    url(r'^doc/(?P<id>\w+)/',views.detail),
    url(r'^docs$',views.docs),
    url(r'^$',views.index), 
    url(r'^upload$',views.upload, name='upload'), 
    url(r'^reconcile$',views.reconcile, name='reconcile'),
    url(r'^conflicts$',views.conflicts, name='conflicts'),
    url(r'^assets/(?P<path>.*)$', "django.views.static.serve",
    {"document_root": os.path.dirname(__file__) + "/static"}),
    url(r'^images/(?P<path>.*)$', "django.views.static.serve",
    {"document_root": os.path.dirname(__file__) + "/static/images"}),
)
