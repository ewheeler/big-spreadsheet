import json
import copy
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

    def key_list(key):
	map_fun = '''function(doc) { emit([doc.%s], doc.%s); }''' % (key, key)
	res = docs.query(map_fun)
	keys = list(set([r.value for r in res.rows]))
	return keys

    def form_filter(**kwargs):
    	try:
	    terms = copy.copy(kwargs)

	    # map with the most limiting term
	    if 'district' in kwargs:
		to_use = "doc.district"
		key = kwargs.pop('district')
	    elif 'cluster' in kwargs:
	        to_use = "doc.cluster"
		key = kwargs.pop('cluster')
	    elif 'codes' in kwargs:
	        to_use = "doc.codes"
		key = kwargs.pop('codes')
	    elif 'province' in kwargs:
	        to_use = "doc.province"
		key = kwargs.pop('province')
	    elif 'organization' in kwargs:
	        to_use = "doc.organization"
		key = kwargs.pop('organization')
	    else:
	        return None

	    form_filter_map = '''function(doc) { emit(%s, doc); }''' % (to_use)
	    res = docs.query(form_filter_map)
	    # remaining terms to limit results
	    limit_by = kwargs
	    reps = []
	    if res.rows is not None:
		for r in res.rows:
		    if key == r.key:
			if len(limit_by) == 0:
			    reps.append(r.id)
			if len(limit_by) > 0:
			    vals = limit_by.values()
			    if set(vals).issubset(set(r.value.values())):
				reps.append(r.id)

	    return terms, reps
	except Exception, e:
	    print 'bang'
	    print e

    doc_keys = ['organization', 'province', 'district', 'cluster', 'codes']
    key_lists = dict(zip( doc_keys ,[key_list(k) for k in doc_keys]))

    if request.method == "POST":
	d = dict(request.POST.items())
	lst = ['', ' ', '0']
	for k, v in list(d.items()):
	    if k in lst or v in lst:
		del d[k]
	terms, rows = form_filter(**d)
	return render_to_response('index.html',{'rows':rows,
	    'key_lists':key_lists, 'terms':terms, 'count': len(rows)})
    return render_to_response('index.html',{'rows':docs,
    	'key_lists':key_lists})

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
                    column_names = [k.lower() for k in sheet.row_values(0)]
                    for r in range(int(sheet.nrows))[1:]:
                        rd = dict(zip(column_names, sheet.row_values(r)))
			rd.update({'date_uploaded':nownow})

                        lst = ['', ' ']
                        for k, v in list(rd.items()):
                            if k in lst or v in lst:
                                del rd[k]
                        docs.save(**rd)
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
