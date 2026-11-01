from django.db import migrations, models

class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [migrations.CreateModel(name="Draft", fields=[
        ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
        ("owner_key", models.UUIDField(editable=False, unique=True)),
        ("markdown_source", models.TextField(blank=True)),
        ("revision", models.PositiveIntegerField(default=0)),
        ("updated_at", models.DateTimeField(auto_now=True)),
    ])]
