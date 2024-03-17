from django.db import models

from tracked_model import tracked


@tracked()
class MyModel(models.Model):

    number = models.IntegerField()
