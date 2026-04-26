from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from PIL import Image

from properties.models import Property
from users.models import CustomUser


class HostListingCreationTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='hostuser',
            email='host@example.com',
            password='testpass123',
            role='host',
        )
        self.client.force_login(self.user)

    def _make_image(self, name='cover.png'):
        buffer = BytesIO()
        Image.new('RGB', (32, 32), color='navy').save(buffer, format='PNG')
        return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')

    def test_host_can_create_listing_with_uploaded_image(self):
        response = self.client.post(
            reverse('hosts:add_listing'),
            data={
                'name': 'Test Stay',
                'description': 'A neat place to stay.',
                'property_type': 'apartment',
                'address': 'Kisumu',
                'city': 'Kisumu',
                'state': 'Kisumu County',
                'country': 'Kenya',
                'latitude': '-0.091701',
                'longitude': '34.767956',
                'price_per_night': '1000',
                'max_guests': '2',
                'bedrooms': '1',
                'beds': '1',
                'bathrooms': '1',
                'sqft': '320',
                'amenities': ['wifi'],
                'check_in_time': '15:00',
                'check_out_time': '11:00',
                'images-TOTAL_FORMS': '5',
                'images-INITIAL_FORMS': '0',
                'images-MIN_NUM_FORMS': '0',
                'images-MAX_NUM_FORMS': '10',
                'images-0-image': self._make_image(),
                'images-0-caption': 'Cover image',
                'images-0-is_primary': 'on',
            },
        )

        self.assertEqual(response.status_code, 302)
        listing = Property.objects.get(name='Test Stay')
        self.assertEqual(listing.images.count(), 1)
