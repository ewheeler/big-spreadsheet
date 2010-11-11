from django.db import models
from django.utils.translation import ugettext_lazy as _

class Upload(models.Model):
    """
    A simple model which stores data about an uploaded document.
    """
    local_document = models.FileField(_("Local Document"), null=True, blank=True, upload_to='~/tmp/')
    date_uploaded = models.DateTimeField(_("Date Uploaded"))
