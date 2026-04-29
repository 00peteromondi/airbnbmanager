from datetime import timedelta

from django.utils import timezone

from bookings.services import initiate_mpesa_checkout

from .models import HostSubscription, HostSubscriptionCharge


def ensure_host_subscription(user):
    subscription, created = HostSubscription.objects.get_or_create(
        host=user,
        defaults={
            'plan': 'growth',
            'status': 'trialing',
            'started_at': timezone.now(),
            'trial_ends_at': timezone.now() + timedelta(days=14),
        },
    )
    if not created:
        subscription.sync_status()
    return subscription


def get_plan_cards():
    catalog = HostSubscription.plan_catalog()
    return [
        {
            'key': key,
            'name': value['name'],
            'price': value['price'],
            'listing_limit': value['listing_limit'],
            'ai_messages': value['ai_messages'],
            'features': value['features'],
            'badge': 'Recommended' if key == 'growth' else 'Premium ops' if key == 'signature' else 'Start smart',
            'description': (
                'A clean starting plan for focused hosts.'
                if key == 'essential'
                else 'Balanced for active BayStays operators.'
                if key == 'growth'
                else 'Built for larger host portfolios and faster ops.'
            ),
        }
        for key, value in catalog.items()
    ]


def apply_subscription_plan(subscription, plan, status='active', mpesa_phone_number=''):
    now = timezone.now()
    subscription.plan = plan
    subscription.status = status
    subscription.mpesa_phone_number = mpesa_phone_number or subscription.mpesa_phone_number
    subscription.started_at = subscription.started_at or now
    subscription.canceled_at = None
    subscription.trial_ends_at = None
    if plan == 'essential':
        subscription.current_period_end = None
        subscription.next_billing_date = None
    else:
        subscription.current_period_end = now + timedelta(days=30)
        subscription.next_billing_date = now + timedelta(days=30)
    subscription.save()
    return subscription


def change_subscription_plan(subscription, plan, phone_number=''):
    if plan == 'essential':
        apply_subscription_plan(subscription, plan, status='active', mpesa_phone_number=phone_number)
        return {'ok': True, 'status': 'active', 'message': 'Your BayStays plan is now Essential.', 'charge': None}

    amount = HostSubscription.plan_catalog()[plan]['price']
    charge = HostSubscriptionCharge.objects.create(
        subscription=subscription,
        plan=plan,
        amount=amount,
        phone_number=phone_number or subscription.mpesa_phone_number or subscription.host.phone_number or '',
        status='initiated',
    )
    result = initiate_mpesa_checkout(
        reference=f'HOSTSUB-{subscription.id}-{charge.id}',
        phone_number=charge.phone_number,
        amount=amount,
        description=f'BayStays {HostSubscription.plan_catalog()[plan]["name"]} plan',
    )
    charge.status = result.get('status', 'failed')
    charge.checkout_request_id = result.get('checkout_request_id', '')
    charge.merchant_request_id = result.get('merchant_request_id', '')
    charge.transaction_reference = result.get('transaction_reference', '')
    charge.failure_reason = result.get('message', '')
    update_fields = [
        'status',
        'checkout_request_id',
        'merchant_request_id',
        'transaction_reference',
        'failure_reason',
        'updated_at',
    ]
    if charge.status == 'paid':
        charge.paid_at = timezone.now()
        update_fields.append('paid_at')
        apply_subscription_plan(subscription, plan, status='active', mpesa_phone_number=charge.phone_number)
    else:
        subscription.metadata = subscription.metadata or {}
        subscription.metadata['pending_plan'] = plan
        subscription.metadata['pending_charge_id'] = charge.id
        subscription.save(update_fields=['metadata', 'updated_at'])
    charge.save(update_fields=update_fields)
    return {
        'ok': charge.status in ['paid', 'initiated'],
        'status': charge.status,
        'message': result.get('message', 'Unable to update your BayStays plan right now.'),
        'charge': charge,
    }
