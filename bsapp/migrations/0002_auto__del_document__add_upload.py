# encoding: utf-8
import datetime
from south.db import db
from south.v2 import SchemaMigration
from django.db import models

class Migration(SchemaMigration):

    def forwards(self, orm):
        
        # Deleting model 'Document'
        db.delete_table('bsapp_document')

        # Adding model 'Upload'
        db.create_table('bsapp_upload', (
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('local_document', self.gf('django.db.models.fields.files.FileField')(max_length=100, null=True, blank=True)),
            ('date_uploaded', self.gf('django.db.models.fields.DateTimeField')()),
        ))
        db.send_create_signal('bsapp', ['Upload'])


    def backwards(self, orm):
        
        # Adding model 'Document'
        db.create_table('bsapp_document', (
            ('local_document', self.gf('django.db.models.fields.files.FileField')(max_length=100, null=True, blank=True)),
            ('id', self.gf('django.db.models.fields.AutoField')(primary_key=True)),
            ('date_uploaded', self.gf('django.db.models.fields.DateTimeField')()),
        ))
        db.send_create_signal('bsapp', ['Document'])

        # Deleting model 'Upload'
        db.delete_table('bsapp_upload')


    models = {
        'bsapp.upload': {
            'Meta': {'object_name': 'Upload'},
            'date_uploaded': ('django.db.models.fields.DateTimeField', [], {}),
            'id': ('django.db.models.fields.AutoField', [], {'primary_key': 'True'}),
            'local_document': ('django.db.models.fields.files.FileField', [], {'max_length': '100', 'null': 'True', 'blank': 'True'})
        }
    }

    complete_apps = ['bsapp']
