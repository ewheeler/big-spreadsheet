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

    def org_cluster(org, clust):
	org_cluster_map = '''function(doc) {
	    emit([doc.organization, doc.cluster], doc);
	}'''
	res = docs.query(org_cluster_map)
	reps = [r for r in res[[org, clust]].rows]
	return reps

    def cluster_prov(clust, prov):
	cluster_prov_map = '''function(doc) {
	    emit([doc.cluster, doc.province], doc);
	}'''
	res = docs.query(cluster_prov_map)
	reps = [r for r in res[[clust, prov]].rows]
	return reps

    def prov_org(prov, org):
	prov_org_map = '''function(doc) {
	    emit([doc.province, doc.organization], doc);
	}'''
	res = docs.query(prov_org_map)
	reps = [r for r in res[[prov,org]].rows]
	return reps

    def orgs():
    	org_map = '''function(doc) {
	    emit([doc.organization], doc.organization);
	}'''
	res = docs.query(org_map)
	reps = list(set([r.value for r in res.rows]))
	return reps

    def provs():
    	prov_map = '''function(doc) {
	    emit([doc.province], doc.province);
	}'''
	res = docs.query(prov_map)
	reps = list(set([r.value for r in res.rows]))
	return reps

    def dists():
    	dist_map = '''function(doc) {
	    emit([doc.district], doc.district);
	}'''
	res = docs.query(dist_map)
	reps = list(set([r.value for r in res.rows]))
	return reps

    def clusts():
    	clust_map = '''function(doc) {
	    emit([doc.cluster], doc.cluster);
	}'''
	res = docs.query(clust_map)
	reps = list(set([r.value for r in res.rows]))
	return reps

    def codes():
    	code_map = '''function(doc) {
	    emit([doc.codes], doc.codes);
	}'''
	res = docs.query(code_map)
	reps = list(set([r.value for r in res.rows]))
	return reps

    def form_filter(**kwargs):
    	try:
	    keys = kwargs.keys()
	    print keys
	    attrs = "doc." + (", doc.".join(keys))
	    print attrs

	    # slice
	    terms = ",".join(kwargs.values())
	    print terms

	    form_filter_map = '''function(doc) { emit([%s], doc); }''' % (attrs)
	    res = docs.query(form_filter_map)
	    len(res)
	    print res
	    reps = [r for r in res[[terms]].rows]
	    len(reps)
	    print reps
	    return reps
	except Exception, e:
	    print 'bang'
	    print Exception
	    print e

    key_lists = {'organizations':orgs(), 'provinces':provs(),
    	'districts':dists(), 'clusters':clusts(), 'codes': codes()}

    if request.method == "POST":
        #title = request.POST['title'].replace(' ','')
        #docs[title] = {'title':title,'text':""}
        #return HttpResponseRedirect(u"/doc/%s/" % title)
	d = dict(request.POST.items())
	print d
	lst = ['', ' ', '0']
	for k, v in list(d.items()):
	    if k in lst or v in lst:
		del d[k]
	print d
	rows = form_filter(**d)
	print rows
	return render_to_response('index.html',{'rows':rows,
	    'key_lists':key_lists})
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
