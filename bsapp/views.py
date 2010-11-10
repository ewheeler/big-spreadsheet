import json
import datetime
import xlrd
from django.http import Http404,HttpResponseRedirect,HttpResponse
from django.shortcuts import render_to_response
from django.utils import simplejson
from couchdb import Server
from . import forms

SERVER = Server('http://127.0.0.1:5984')
if (len(SERVER) == 0):
    SERVER.create('docs')

def index(request):
    docs = SERVER['docs']
    if request.method == "POST":
        title = request.POST['title'].replace(' ','')
        docs[title] = {'title':title,'text':""}
        return HttpResponseRedirect(u"/doc/%s/" % title)
    return render_to_response('index.html',{'rows':docs})

def docs(request):
    docs = SERVER['docs']
    return HttpResponse((docs), 'application/javascript')

def detail(request,id):
    docs = SERVER['docs']
    try:
        doc = docs[id]
    except ResourceNotFound:
        raise Http404        
    if request.method =="POST":
        try:
            post_data = dict(request.POST)
            post_data = dict(zip(post_data.keys(),[v[0] for k,v in post_data.iteritems()]))
            new_key = post_data.pop('new-key')
            new_val = post_data.pop('new-val')
            if new_key or new_val not in [None, '']:
                post_data.update({new_key:new_val})
            doc.update(post_data)
            docs.save(doc)
        except Exception, e:
            print 'BANG'
            print e
            import ipdb;ipdb.set_trace()

    return render_to_response('detail.html',{'row':doc})
    #return HttpResponse(simplejson.dumps(doc), 'application/javascript')

def upload(req):
    docs = SERVER['docs']
    if req.method == 'POST':
        form = forms.UploadForm(req.POST, req.FILES)
        if form.is_valid():
            try:
                f = form.save(commit=False)
                nownow = datetime.datetime.utcnow()
                f.date_uploaded = nownow
                f.save()
                book = xlrd.open_workbook(f.local_document.file.name)
                sheets = book.sheet_names()
                sheet = None
                for s in sheets:
                    if s in ['Sheet1']:
                        sheet = book.sheet_by_name(s)
                        break
                if sheet is not None:
                    column_names = sheet.row_values(0)
                    for r in range(int(sheet.nrows))[1:]:
                        rd = dict(zip(column_names, sheet.row_values(r)))
                        rd.update({'uploaded_at': nownow})
                        docs.create(rd)
            except Exception, e:
                print 'BANG'
                print Exception
                print e
                import ipdb;ipdb.set_trace()
            return HttpResponseRedirect('/')
    else:
        form = forms.UploadForm()
    return render_to_response("upload.html",\
            {"form": form})
