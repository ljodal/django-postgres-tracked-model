from django.db import models

from tracked_model import tracked
from tracked_model.models import ModelVersion

# Simple case, just a single tracked model
@tracked()
class MyModel(models.Model):
    number = models.IntegerField()

# Complex case, hierachy of tracked models
class AuthorVersion(ModelVersion):
    author = models.OneToOneField(
        "Author",
        primary_key=True,
        related_name="version",
        on_delete=models.CASCADE,
    )

@tracked(version_model=AuthorVersion)
class Author(models.Model):
    name = models.CharField(max_length=200)


@tracked(parent=Author)
class Book(models.Model):
    title = models.CharField(max_length=200)
    author = models.ForeignKey(
        Author,
        related_name="books",
        on_delete=models.CASCADE,
    )
