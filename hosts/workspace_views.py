from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string

from properties.models import Property
from users.notifications import notify_report_ready, notify_subscription_update

from .reporting import build_host_report, build_listing_report, build_pdf_response
from .services import apply_subscription_plan, change_subscription_plan, ensure_host_subscription, get_plan_cards
from .views import _ensure_host_mode


def _subscription_context(user):
    subscription = ensure_host_subscription(user)
    recent_charges = subscription.charges.all()[:6]
    latest_charge = subscription.charges.order_by('-updated_at').values_list('updated_at', flat=True).first()
    latest_stamp = max(
        [stamp for stamp in [subscription.updated_at, latest_charge] if stamp is not None],
        default=None,
    )
    return {
        'subscription': subscription,
        'plan_cards': get_plan_cards(),
        'recent_charges': recent_charges,
        'live_version': latest_stamp.isoformat() if latest_stamp else 'none',
    }


@login_required
def subscription_manage(request):
    host_gate = _ensure_host_mode(request)
    if host_gate:
        return host_gate
    context = _subscription_context(request.user)
    subscription = context['subscription']
    if request.method == 'POST':
        plan = request.POST.get('plan', '').strip()
        phone_number = request.POST.get('mpesa_phone_number', '').strip()
        if plan not in {'essential', 'growth', 'signature'}:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'ok': False, 'error': 'Please choose a valid BayStays host plan.'}, status=400)
            messages.error(request, 'Please choose a valid BayStays host plan.')
            return redirect('hosts:subscription_manage')
        result = change_subscription_plan(subscription, plan, phone_number=phone_number)
        if result['ok']:
            notify_subscription_update(
                subscription,
                title='Host subscription updated',
                body=result['message'],
                level='success' if result['status'] == 'paid' or plan == 'essential' else 'info',
            )
            if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
                messages.success(request, result['message'])
        else:
            notify_subscription_update(
                subscription,
                title='Host subscription update failed',
                body=result['message'],
                level='urgent',
            )
            if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
                messages.error(request, result['message'])
        context = _subscription_context(request.user)
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            if result['status'] == 'initiated':
                message = (
                    f"{result['message']} Check your phone for the M-Pesa prompt to finish moving to the "
                    f"{dict(subscription.PLAN_CHOICES).get(plan, plan.title())} plan."
                )
            else:
                message = result['message']
            return JsonResponse({
                'ok': result['ok'],
                'message': message,
                'html': render_to_string('hosts/_subscription_manage_content.html', context, request=request),
                'version': context['live_version'],
            }, status=200 if result['ok'] else 400)
        return redirect('hosts:subscription_manage')

    return render(request, 'hosts/subscription_manage.html', context)


@login_required
def subscription_manage_live(request):
    host_gate = _ensure_host_mode(request)
    if host_gate:
        return JsonResponse({'redirect_url': '/hosts/dashboard/'}, status=403)
    context = _subscription_context(request.user)
    return JsonResponse({
        'html': render_to_string('hosts/_subscription_manage_content.html', context, request=request),
        'version': context['live_version'],
    })


@login_required
def host_performance(request):
    host_gate = _ensure_host_mode(request)
    if host_gate:
        return host_gate
    ensure_host_subscription(request.user)
    report = build_host_report(request.user)
    return render(request, 'hosts/host_performance.html', {
        'report': report,
        'subscription': ensure_host_subscription(request.user),
    })


@login_required
def download_host_performance_pdf(request):
    host_gate = _ensure_host_mode(request)
    if host_gate:
        return host_gate
    report = build_host_report(request.user)
    notify_report_ready(
        request.user,
        'Host performance PDF generated',
        'Your portfolio-level BayStays performance export is ready.',
        action_url='/hosts/performance/',
    )
    return build_pdf_response(
        filename='baystays-host-performance.pdf',
        title='Host Performance Summary',
        subtitle='Portfolio-level hosting performance snapshot',
        sections=[
            {
                'heading': 'Portfolio snapshot',
                'intro': 'A concise operating summary for your full BayStays host portfolio.',
                'rows': [
                    ('Listings', report['metrics']['properties_count']),
                    ('Active listings', report['metrics']['active_listings']),
                    ('Bookings', report['metrics']['bookings_count']),
                    ('Pending requests', report['metrics']['pending_count']),
                    ('Completed stays', report['metrics']['completed_count']),
                    ('Gross revenue', f"KES {report['metrics']['gross_revenue']:,.0f}"),
                    ('Paid revenue', f"KES {report['metrics']['paid_revenue']:,.0f}"),
                    ('Average rating', f"{report['metrics']['average_rating']:.1f}"),
                ],
            },
            {
                'heading': 'Recommendations',
                'notes': report['recommendations'],
            },
        ],
    )


@login_required
def listing_performance(request, property_id):
    host_gate = _ensure_host_mode(request)
    if host_gate:
        return host_gate
    property_obj = get_object_or_404(Property, id=property_id, owner=request.user)
    report = build_listing_report(property_obj)
    return render(request, 'hosts/listing_performance.html', {
        'report': report,
        'property': property_obj,
    })


@login_required
def download_listing_performance_pdf(request, property_id):
    host_gate = _ensure_host_mode(request)
    if host_gate:
        return host_gate
    property_obj = get_object_or_404(Property, id=property_id, owner=request.user)
    report = build_listing_report(property_obj)
    notify_report_ready(
        request.user,
        f'{property_obj.name} report generated',
        'Your listing-level BayStays performance export is ready.',
        action_url=f'/hosts/properties/{property_obj.id}/performance/',
    )
    return build_pdf_response(
        filename=f'baystays-listing-{property_obj.id}-performance.pdf',
        title='Listing Performance Summary',
        subtitle=property_obj.name,
        sections=[
            {
                'heading': 'Listing snapshot',
                'intro': 'Performance coverage for this individual BayStays listing.',
                'rows': [
                    ('Property', property_obj.name),
                    ('Location', f'{property_obj.city}, {property_obj.country}'),
                    ('Total bookings', report['metrics']['total_bookings']),
                    ('Confirmed', report['metrics']['confirmed_count']),
                    ('Completed', report['metrics']['completed_count']),
                    ('Cancelled', report['metrics']['cancelled_count']),
                    ('Gross revenue', f"KES {report['metrics']['gross_revenue']:,.0f}"),
                    ('Paid revenue', f"KES {report['metrics']['paid_revenue']:,.0f}"),
                    ('Avg stay length', f"{report['metrics']['average_stay_length']} nights"),
                    ('Occupancy', f"{report['metrics']['occupancy_rate']}%"),
                ],
            },
            {
                'heading': 'Recommendations',
                'notes': report['recommendations'],
            },
        ],
    )
