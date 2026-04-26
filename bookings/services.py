import base64
import json
import uuid
from datetime import datetime
from urllib import error, parse, request

from django.conf import settings
from django.utils import timezone


def _mpesa_setting(name, default=''):
    return getattr(settings, name, default) or default


def _token_headers(token):
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }


def _generate_reference(prefix):
    return f'{prefix}-{uuid.uuid4().hex[:12].upper()}'


def _mpesa_base_url():
    env = _mpesa_setting('MPESA_ENV', 'sandbox').lower()
    if env == 'production':
        return 'https://api.safaricom.co.ke'
    return 'https://sandbox.safaricom.co.ke'


def _mpesa_timestamp():
    return timezone.now().strftime('%Y%m%d%H%M%S')


def _get_access_token():
    consumer_key = _mpesa_setting('MPESA_CONSUMER_KEY')
    consumer_secret = _mpesa_setting('MPESA_CONSUMER_SECRET')
    if not consumer_key or not consumer_secret:
        return None, 'Missing M-Pesa API credentials.'

    credentials = base64.b64encode(f'{consumer_key}:{consumer_secret}'.encode('utf-8')).decode('utf-8')
    token_request = request.Request(
        f'{_mpesa_base_url()}/oauth/v1/generate?grant_type=client_credentials',
        headers={'Authorization': f'Basic {credentials}'},
        method='GET',
    )
    try:
        with request.urlopen(token_request, timeout=15) as response:
            payload = json.loads(response.read().decode('utf-8'))
            return payload.get('access_token'), None
    except error.HTTPError as exc:
        return None, f'M-Pesa token request failed with {exc.code}.'
    except Exception as exc:  # pragma: no cover - network/runtime dependent
        return None, str(exc)


def initiate_mpesa_payment(*, booking, phone_number, amount):
    simulate = _mpesa_setting('MPESA_SIMULATE', 'true' if settings.DEBUG else 'false').lower() == 'true'
    if simulate:
        return {
            'ok': True,
            'status': 'paid',
            'checkout_request_id': _generate_reference('CHK'),
            'merchant_request_id': _generate_reference('MER'),
            'transaction_reference': _generate_reference('MPESA'),
            'message': 'M-Pesa payment captured in local simulation mode.',
            'paid_at': timezone.now(),
        }

    access_token, error_message = _get_access_token()
    if not access_token:
        return {'ok': False, 'status': 'failed', 'message': error_message or 'Unable to authenticate with M-Pesa.'}

    shortcode = _mpesa_setting('MPESA_SHORTCODE')
    passkey = _mpesa_setting('MPESA_PASSKEY')
    callback_url = _mpesa_setting('MPESA_CALLBACK_URL', 'https://example.com/mpesa/callback/')
    if not shortcode or not passkey:
        return {'ok': False, 'status': 'failed', 'message': 'Missing M-Pesa shortcode or passkey.'}

    timestamp = _mpesa_timestamp()
    password = base64.b64encode(f'{shortcode}{passkey}{timestamp}'.encode('utf-8')).decode('utf-8')
    payload = {
        'BusinessShortCode': shortcode,
        'Password': password,
        'Timestamp': timestamp,
        'TransactionType': 'CustomerPayBillOnline',
        'Amount': int(round(float(amount))),
        'PartyA': phone_number,
        'PartyB': shortcode,
        'PhoneNumber': phone_number,
        'CallBackURL': callback_url,
        'AccountReference': str(booking.id),
        'TransactionDesc': f'BayStays booking #{booking.id}',
    }
    stk_request = request.Request(
        f'{_mpesa_base_url()}/mpesa/stkpush/v1/processrequest',
        data=json.dumps(payload).encode('utf-8'),
        headers=_token_headers(access_token),
        method='POST',
    )
    try:
        with request.urlopen(stk_request, timeout=20) as response:
            data = json.loads(response.read().decode('utf-8'))
            return {
                'ok': True,
                'status': 'initiated',
                'checkout_request_id': data.get('CheckoutRequestID', ''),
                'merchant_request_id': data.get('MerchantRequestID', ''),
                'transaction_reference': _generate_reference('MPESA'),
                'message': data.get('CustomerMessage') or 'M-Pesa payment request sent to your phone.',
                'paid_at': None,
            }
    except error.HTTPError as exc:
        try:
            detail = exc.read().decode('utf-8')
        except Exception:
            detail = ''
        return {
            'ok': False,
            'status': 'failed',
            'message': detail or f'M-Pesa STK push failed with {exc.code}.',
        }
    except Exception as exc:  # pragma: no cover - network/runtime dependent
        return {
            'ok': False,
            'status': 'failed',
            'message': str(exc),
        }


def simulate_withdrawal_payout():
    return {
        'status': 'paid',
        'message': 'Withdrawal queued successfully in simulation mode.',
        'reference': _generate_reference('WD'),
        'processed_at': timezone.now(),
    }
