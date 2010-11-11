#!/usr/bin/env python
# vim: ai ts=4 sts=4 et sw=4
from django import forms

from .models import Upload

class UploadForm(forms.ModelForm):

    local_document = forms.FileField(
        required=False)

    class Meta:
        model = Upload
        fields = ('local_document',)
