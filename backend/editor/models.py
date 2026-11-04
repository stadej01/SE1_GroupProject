from django.db import models

class Draft(models.Model):
    """One draft per browser session until project/user models are integrated."""
    owner_key = models.UUIDField(unique=True, editable=False)
    markdown_source = models.TextField(blank=True)
    revision = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)
