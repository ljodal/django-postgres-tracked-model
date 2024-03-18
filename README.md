# Django Postgres Tracked Model

This is a Django implementation of [Cognite's txid-syncing](https://github.com/cognitedata/txid-syncing). It's an approach to reliabliy sync data between Postgres and other systems, for example ElasticSearch. To keep track of changes a version table is added that tracks which transaction last updated each row in a tracked table.

## Usage

> [!CAUTION]
> This library is very much work-in-progress. I'd recommend not using it in anything production critical

1. First you need to install the application in your Django settings file
   ```python
   INSTALLED_APPLICATIONS = [
       ...,
       "tracked_model",
   ]
   ```
2. Next you add the decorator to the model(s) you want to sync/track
   ```python
   from django.db import models
   from tracked_model import tracked

   @tracked()
   class MyModel(models.Model):
       ...
   ```
3. Create new migrations. This will create a new model with metadata about the syncing
   ```bash
   ./manage.py makemigrations
   ```
3. Create a new migration and add triggers and backfill data
   ```bash
   ./manage.py makemigrations --empty --name add_tracking my_app
   ```
   Edit the migration and add operations to track changes and backfill for existing rows
   ```python
   from tracked_model.operations import AddVersionTracking, BackfillModelVersion
   
   class Migration(migrations.Migration):
       operations = [
           # Note: You'll probably want to do this in two separate migrations
           AddVersionTracking(tracked_model="MyModel", version_model="MyModelVersion"),
           BackfillModelVersion(tracked_model="MyModel"),
       ]
   ```

Now you can start streaming changes to your models:

```python
import time
from tracked_model import get_changed_objects

qs = MyModel.objects.all()
changes, cursor = get_changed_objects(cursor=None, limit=10, queryset=qs)
while True:
    if not changes:
        time.sleep(5)
    else:
        print(changes)

    changes, cursor = get_changed_objects(cursor=cursor, limit=10, queryset=qs)
```

You can send in any queryset you want. The changes return value will be a list of objects returned from the queryset. You can send in any kind of queryset, e.g. using `.values()`, depending on what you want to have out.
