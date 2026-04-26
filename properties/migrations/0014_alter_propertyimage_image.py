from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('properties', '0013_remove_property_baths_remove_property_price_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='propertyimage',
            name='image',
            field=models.ImageField(upload_to='property_images/'),
        ),
    ]
