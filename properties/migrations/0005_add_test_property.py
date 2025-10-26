from django.db import migrations
from django.utils import timezone

def create_test_property(apps, schema_editor):
    Property = apps.get_model('properties', 'Property')
    CustomUser = apps.get_model('users', 'CustomUser')
    
    # Get or create a test user
    test_user, created = CustomUser.objects.get_or_create(
        username='testhost',
        email='testhost@example.com',
        defaults={
            'password': 'testpass123',
            'is_active': True,
            'role': 'host'
        }
    )
    
    # Create a test property
    Property.objects.get_or_create(
        name='Luxury Villa with Pool',
        defaults={
            'owner': test_user,
            'description': 'A beautiful villa with a private pool and garden',
            'property_type': 'villa',
            'address': '123 Test Street',
            'city': 'Nairobi',
            'state': 'Nairobi',
            'country': 'Kenya',
            'price_per_night': 15000.00,
            'max_guests': 6,
            'bedrooms': 3,
            'bathrooms': 2,
            'amenities': ['wifi', 'pool', 'kitchen', 'parking'],
            'is_active': True
        }
    )

def remove_test_property(apps, schema_editor):
    Property = apps.get_model('properties', 'Property')
    Property.objects.filter(name='Luxury Villa with Pool').delete()

class Migration(migrations.Migration):
    dependencies = [
        ('properties', '0004_property_reviews'),
    ]

    operations = [
        migrations.RunPython(create_test_property, remove_test_property),
    ]