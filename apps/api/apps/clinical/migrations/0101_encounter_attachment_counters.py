from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('clinical', '0100_auto_last'),
    ]

    operations = [
        migrations.AddField(
            model_name='encounter',
            name='photo_count_cached',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='encounter',
            name='document_count_cached',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='encounter',
            name='has_photos_cached',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='encounter',
            name='has_documents_cached',
            field=models.BooleanField(default=False),
        ),
    ]
