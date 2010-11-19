#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4 encoding=utf-8

import json
import copy
import datetime
import hashlib
import re
import unicodedata

#from couchdb import Server
from couchdbkit import *
from restkit import SimplePool
import xlrd

from django.http import Http404,HttpResponseRedirect,HttpResponse
from django.shortcuts import render_to_response
from django.utils import simplejson


from . import forms
from bsapp.reconcile import *

#SERVER = Server('http://127.0.0.1:5984')
#if (len(SERVER) == 0):
#    SERVER.create('docs')

# set a threadsafe pool to keep 2 connections alives
pool = SimplePool(keepalive=2)

# server object
server = Server(pool_instance=pool)

# create database
docs = server.get_or_create_db("docs")


def index(request):
    #docs = SERVER['docs']
    docs = server.get_or_create_db("docs")

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
    #docs = SERVER['docs']
    docs = server.get_or_create_db("docs")
    return HttpResponse((docs), 'application/javascript')

def detail(request,id):
    #docs = SERVER['docs']
    docs = server.get_or_create_db("docs")
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

def unq_ordered(seq, idfun=None):
    # order preserving
    if idfun is None:
        def idfun(x): return x
    seen = {}
    result = []
    for item in seq:
        marker = idfun(item)
        # in old Python versions:
        # if seen.has_key(marker)
        # but in new ones:
        if marker in seen: continue
        seen[marker] = 1
        result.append(item)
    return result

def fingerprint(string):
    # replace weird unicode characters with similar looking ones, encode as ascii
    # TODO this doesnt work quite right
    a = unicodedata.normalize('NFKC', string).encode('ascii','ignore')
    # remove leading and trailing whitespace
    f = string.strip()
    # lowercase
    f = f.lower()
    # remove everything but letters and numbers and whitespace
    f = re.sub("[^a-zA-Z0-9\s]", "", f)
    # sort tokens and remove duplicates
    l = unq_ordered(sorted(f.split()))
    # join tokens into string
    s = "".join(l)
    return s


def upload(req):
    #docs = SERVER['docs']
    docs = server.get_or_create_db("docs")
    if req.method == 'POST':
        form = forms.UploadForm(req.POST, req.FILES)
        if form.is_valid():
            try:
                f = form.save(commit=False)
                nownow = datetime.datetime.utcnow().replace(microsecond=0).isoformat()
                nownow = nownow.replace('T', ' ')

                f.date_uploaded = nownow
                f.save()
                book = xlrd.open_workbook(f.local_document.file.name)

                if book.datemode not in (0,1):
                    return "oops. unknown datemode!"

                def xldate_to_datetime(xldate):
                    return datetime.datetime(*xlrd.xldate_as_tuple(xldate, book.datemode))

                def xldate_to_date(xldate):
                    return xldate_to_datetime(xldate).date()

                sheets = book.sheet_names()
                sheet = None
                for s in sheets:
                    if s in ['Sheet1']:
                        sheet = book.sheet_by_name(s)
                        break
                if sheet is not None:
                    column_names = [k.lower() for k in sheet.row_values(0)]
                    conflicts = []
                    product_errors = []
                    country_errors = []
                    for r in range(int(sheet.nrows))[1:]:
                        # dictionary mapping column names to row content
                        rd = dict(zip(column_names, sheet.row_values(r)))

                        # remove blank items
                        # TODO include things like N/A, None, etc
                        lst = ['', ' ']
                        for k, v in list(rd.items()):
                            if k in lst or v in lst:
                                del rd[k]

                        # skip blank rows
                        if len(rd.keys()) ==0:
                            continue

                        # convert xldates to dates
                        # XXX .isoformat() ??
                        if 'input date' in rd:
                            conv_input_date = xldate_to_date(rd['input date'])
                            rd.update({'input date': conv_input_date.isoformat()})

                        if 'input date mon-yyyy' in rd:
                            conv_input_date_my = xldate_to_date(rd['input date mon-yyyy'])
                            rd.update({'input date': conv_input_date_my.isoformat()})

                        # add date uploaded to dict
                        rd.update({'date_uploaded':nownow})

                        if 'product' in rd:
                            reconciled_product, product_result = reconcile_product(rd['product'])
                        if 'country' in rd:
                            reconciled_country, country_result = reconcile_country(rd['country'])

                        if reconciled_product and reconciled_country:
                            # generate hash for _id
                            h = hashlib.md5()
                            h.update(country_result)
                            h.update(product_result)
                            h.update(rd['yyyy-ww'])
                            if 'supplier' in rd:
                                h.update(rd['supplier'])
                            if 'gavi/ non gavi' in rd:
                                h.update(rd['gavi/ non gavi'])
                            if 'comment' in rd:
                                h.update(rd['comment'])
                            if 'campaign type' in rd:
                                h.update(rd['campaign type'])
                            _id = h.hexdigest()

                            rd.update({u'_id': _id})

                            # attempt to fetch a document
                            # with this id
                            try:
                                collision = docs.get(_id)
                            except Exception, e:
                                collision = None

                            if collision is None:
                                # save to database
                                docs.save_doc(rd)
                            else:
                                conflicts.append({"existing":collision, "new": rd})
                        else:
                            if not reconciled_product:
                                product_errors.append(product_result)
                            if not reconciled_country:
                                country_errors.append(country_result)
                    print str(len(conflicts)) + " conflicts"
                    print str(len(product_errors)) + " product errors"
                    print str(len(country_errors)) + " country errors"
                    import ipdb; ipdb.set_trace()
                    return render_to_response("reconcile.html",
                        {"conflicts": conflicts})

            except Exception, e:
                print 'BANG'
                print e
                import ipdb;ipdb.set_trace()
            return HttpResponseRedirect('/')
    else:
        form = forms.UploadForm()
    return render_to_response("upload.html",\
            {"form": form})

def reconcile(req):
    return render_to_response("reconcile.html")

def conflicts(req):
    conf = {'conflicts': [{'new': {u'product group': u'YF', u'input date': '2010-04-01', u'type of activity': u'Routine', u'campaign type': u'Co-financing', u'% of lta alloc- forecast': 3.3663366336633667, u'doses- on po': 0.0, u'ins': u'YES', u'vvm status or device split': u'Incl. VVM', u'input file details': u'10_01_31 Backup Allocation Table YF.xlsx - 10-12 YF', u'gavi/ non gavi': u'Non GAVI', u'total vials': 8500.0, u'% of lta alloc- total': 3.3663366336633667, u'input date mon-yyyy': 40269.0, u'total doses': 85000.0, u'yyyy-mm': u' 2010-04', u'processing date n time': 40211.689710648148, u'supplier': u'Sanofi 42103232', 'date_uploaded': '2010-11-18 17:11:59', u'% of lta alloc- on po': 0.0, u'product': u'YF-10', u'source country': u'France', u'value of quantity on forecast and po': 79900.0, u'doses- forecast ': 85000.0, u'file type': u'Monthly', u'region': u'WCARO', u'yyyy': 2010.0, u'vials - forecast': 8500.0, u'lta allocation': 2525000.0, u'doses/ vial': 10.0, u'country': u'Niger', u'price/vial': 9.4000000000000004, u'order type': u'PS', u'_id': 'd48f6b604035f1ba421c24db9fd7f6be', u'yyyy-ww': u' 2010-13', u'comment ': 10009574.0}, 'existing': {'product group': 'YF', 'input date': '2010-04-01', 'total vials': 41320.0, 'campaign type': 'Co-financing', '_rev': '1-7fd256cf65dd18733f9d1051f97859e7', 'doses- on po': 0.0, 'ins': 'YES', 'vvm status or device split': 'Incl. VVM', 'input file details': '10_01_31 Backup Allocation Table YF.xlsx - 10-12 YF', 'gavi/ non gavi': 'Non GAVI', 'type of activity': 'Routine', '% of lta alloc- total': 16.364356435643565, '% of lta alloc- on po': 0.0, 'yyyy-mm': ' 2010-04', 'processing date n time': 40211.689710648148, 'supplier': 'Sanofi 42103232', '% of lta alloc- forecast': 16.364356435643565, 'date_uploaded': '2010-11-18 17:11:59', 'input date mon-yyyy': 40269.0, 'product': 'YF-10', 'value of quantity on forecast and po': 388408.0, 'doses- forecast ': 413200.0, 'source country': 'France', 'file type': 'Monthly', 'yyyy': 2010.0, 'vials - forecast': 41320.0, 'doses/ vial': 10.0, 'country': 'Niger', 'region': 'WCARO', 'lta allocation': 2525000.0, 'total doses': 413200.0, 'price/vial': 9.4000000000000004, 'order type': 'PS', '_id': 'd48f6b604035f1ba421c24db9fd7f6be', 'yyyy-ww': ' 2010-13', 'comment ': 10009069.0}}, {'new': {u'product group': u'YF', u'input date': '2010-04-01', u'type of activity': u'Routine', u'% of lta alloc- forecast': 9.2594059405940587, u'doses- on po': 0.0, u'ins': u'YES', u'vvm status or device split': u'Incl. VVM', u'input file details': u'10_02_08 Backup Allocation Table YF.xlsx - 10-12 YF', u'gavi/ non gavi': u'GAVI', u'total vials': 23380.0, u'% of lta alloc- total': 9.2594059405940587, u'input date mon-yyyy': 40269.0, u'total doses': 233800.0, u'yyyy-mm': u' 2010-04', u'processing date n time': 40218.53334490741, u'supplier': u'Sanofi 42103232', 'date_uploaded': '2010-11-18 17:11:59', u'% of lta alloc- on po': 0.0, u'product': u'YF-10', u'source country': u'France', u'value of quantity on forecast and po': 219772.0, u'doses- forecast ': 233800.0, u'file type': u'Monthly', u'region': u'WCARO', u'yyyy': 2010.0, u'vials - forecast': 23380.0, u'lta allocation': 2525000.0, u'doses/ vial': 10.0, u'country': u'Niger', u'price/vial': 9.4000000000000004, u'order type': u'PS', u'_id': 'b5d5433df80ab3fda0748cb628d400f8', u'yyyy-ww': u' 2010-13'}, 'existing': {'product group': 'YF', 'input date': '2010-04-01', 'total vials': 27680.0, '_rev': '1-6d8a49f774e55412176638269168f27b', 'doses- on po': 0.0, 'ins': 'YES', 'vvm status or device split': 'Incl. VVM', 'input file details': '10_01_31 Backup Allocation Table YF.xlsx - 10-12 YF', 'gavi/ non gavi': 'GAVI', 'type of activity': 'Routine', '% of lta alloc- total': 10.962376237623763, '% of lta alloc- on po': 0.0, 'yyyy-mm': ' 2010-04', 'processing date n time': 40211.689710648148, 'supplier': 'Sanofi 42103232', '% of lta alloc- forecast': 10.962376237623763, 'date_uploaded': '2010-11-18 17:11:59', 'input date mon-yyyy': 40269.0, 'product': 'YF-10', 'value of quantity on forecast and po': 260192.0, 'doses- forecast ': 276800.0, 'source country': 'France', 'file type': 'Monthly', 'yyyy': 2010.0, 'vials - forecast': 27680.0, 'doses/ vial': 10.0, 'country': 'Niger', 'region': 'WCARO', 'lta allocation': 2525000.0, 'total doses': 276800.0, 'price/vial': 9.4000000000000004, 'order type': 'PS', '_id': 'b5d5433df80ab3fda0748cb628d400f8', 'yyyy-ww': ' 2010-13'}}, {'new': {u'product group': u'YF', u'input date': '2010-02-01', u'type of activity': u'Routine', u'campaign type': u'Co-financing', u'% of lta alloc- forecast': 3.3663366336633667, u'doses- on po': 0.0, u'ins': u'YES', u'vvm status or device split': u'Incl. VVM', u'input file details': u'10_02_08 Backup Allocation Table YF.xlsx - 10-12 YF', u'gavi/ non gavi': u'Non GAVI', u'total vials': 8500.0, u'% of lta alloc- total': 3.3663366336633667, u'input date mon-yyyy': 40210.0, u'total doses': 85000.0, u'yyyy-mm': u' 2010-02', u'processing date n time': 40218.533356481479, u'supplier': u'Sanofi 42103232', 'date_uploaded': '2010-11-18 17:11:59', u'% of lta alloc- on po': 0.0, u'product': u'YF-10', u'source country': u'France', u'value of quantity on forecast and po': 79900.0, u'doses- forecast ': 85000.0, u'file type': u'Monthly', u'region': u'WCARO', u'yyyy': 2010.0, u'vials - forecast': 8500.0, u'lta allocation': 2525000.0, u'doses/ vial': 10.0, u'country': u'Niger', u'price/vial': 9.4000000000000004, u'order type': u'PS', u'_id': '94a2f0004349491a0c0b86ef8c90b208', u'yyyy-ww': u' 2010-05', u'comment ': 10009574.0}, 'existing': {'product group': 'YF', 'input date': '2010-02-01', 'total vials': 8500.0, 'campaign type': 'Co-financing', '_rev': '1-05e1edb295e630c66800100b31236eff', 'doses- on po': 0.0, 'ins': 'YES', 'vvm status or device split': 'Incl. VVM', 'input file details': '10_01_31 Backup Allocation Table YF.xlsx - 10-12 YF', 'gavi/ non gavi': 'Non GAVI', 'type of activity': 'Routine', '% of lta alloc- total': 3.3663366336633667, '% of lta alloc- on po': 0.0, 'yyyy-mm': ' 2010-02', 'processing date n time': 40211.689710648148, 'supplier': 'Sanofi 42103232', '% of lta alloc- forecast': 3.3663366336633667, 'date_uploaded': '2010-11-18 17:11:59', 'input date mon-yyyy': 40210.0, 'product': 'YF-10', 'value of quantity on forecast and po': 79900.0, 'doses- forecast ': 85000.0, 'source country': 'France', 'file type': 'Monthly', 'yyyy': 2010.0, 'vials - forecast': 8500.0, 'doses/ vial': 10.0, 'country': 'Niger', 'region': 'WCARO', 'lta allocation': 2525000.0, 'total doses': 85000.0, 'price/vial': 9.4000000000000004, 'order type': 'PS', '_id': '94a2f0004349491a0c0b86ef8c90b208', 'yyyy-ww': ' 2010-05', 'comment ': 10009574.0}}, {'new': {u'product group': u'YF', u'input date': '2010-04-01', u'type of activity': u'Routine', u'campaign type': u'Co-financing', u'% of lta alloc- forecast': 16.364356435643565, u'doses- on po': 0.0, u'ins': u'YES', u'vvm status or device split': u'Incl. VVM', u'input file details': u'10_02_08 Backup Allocation Table YF.xlsx - 10-12 YF', u'gavi/ non gavi': u'Non GAVI', u'total vials': 41320.0, u'% of lta alloc- total': 16.364356435643565, u'input date mon-yyyy': 40269.0, u'total doses': 413200.0, u'yyyy-mm': u' 2010-04', u'processing date n time': 40218.533356481479, u'supplier': u'Sanofi 42103232', 'date_uploaded': '2010-11-18 17:11:59', u'% of lta alloc- on po': 0.0, u'product': u'YF-10', u'source country': u'France', u'value of quantity on forecast and po': 388408.0, u'doses- forecast ': 413200.0, u'file type': u'Monthly', u'region': u'WCARO', u'yyyy': 2010.0, u'vials - forecast': 41320.0, u'lta allocation': 2525000.0, u'doses/ vial': 10.0, u'country': u'Niger', u'price/vial': 9.4000000000000004, u'order type': u'PS', u'_id': 'd48f6b604035f1ba421c24db9fd7f6be', u'yyyy-ww': u' 2010-13', u'comment ': 10009069.0}, 'existing': {'product group': 'YF', 'input date': '2010-04-01', 'total vials': 41320.0, 'campaign type': 'Co-financing', '_rev': '1-7fd256cf65dd18733f9d1051f97859e7', 'doses- on po': 0.0, 'ins': 'YES', 'vvm status or device split': 'Incl. VVM', 'input file details': '10_01_31 Backup Allocation Table YF.xlsx - 10-12 YF', 'gavi/ non gavi': 'Non GAVI', 'type of activity': 'Routine', '% of lta alloc- total': 16.364356435643565, '% of lta alloc- on po': 0.0, 'yyyy-mm': ' 2010-04', 'processing date n time': 40211.689710648148, 'supplier': 'Sanofi 42103232', '% of lta alloc- forecast': 16.364356435643565, 'date_uploaded': '2010-11-18 17:11:59', 'input date mon-yyyy': 40269.0, 'product': 'YF-10', 'value of quantity on forecast and po': 388408.0, 'doses- forecast ': 413200.0, 'source country': 'France', 'file type': 'Monthly', 'yyyy': 2010.0, 'vials - forecast': 41320.0, 'doses/ vial': 10.0, 'country': 'Niger', 'region': 'WCARO', 'lta allocation': 2525000.0, 'total doses': 413200.0, 'price/vial': 9.4000000000000004, 'order type': 'PS', '_id': 'd48f6b604035f1ba421c24db9fd7f6be', 'yyyy-ww': ' 2010-13', 'comment ': 10009069.0}}]}
    data = json.dumps(conf)
    return HttpResponse(data)
