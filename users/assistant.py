import json
import logging
import os
import re
from urllib import error, request
from urllib.parse import urlsplit

from django.conf import settings
from django.db import models
from django.db.models import Avg, Sum
from django.urls import Resolver404, resolve, reverse

from bookings.models import Booking, BookingPayment
from hosts.models import Host, HostSubscription
from properties.models import Property

from .models import AssistantChat, Conversation, Notification

logger = logging.getLogger(__name__)


def _history_for_model(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return []
    return list(
        AssistantChat.objects.filter(user=user).order_by('-created_at').values('role', 'content', 'metadata')[:12]
    )[::-1]


def persist_assistant_exchange(user, prompt, response):
    if not user or not getattr(user, 'is_authenticated', False):
        return
    AssistantChat.objects.create(user=user, role='user', content=prompt)
    AssistantChat.objects.create(
        user=user,
        role='assistant',
        content=response.get('text', ''),
        metadata={
            'suggestions': response.get('suggestions', []),
            'highlights': response.get('highlights', []),
        },
    )


def _get_subscription(user):
    if not user or user.role not in ['host', 'both']:
        return None
    return HostSubscription.objects.filter(host=user).first()


def _build_snapshot(user):
    snapshot = {
        'is_authenticated': bool(user and getattr(user, 'is_authenticated', False)),
        'name': user.get_display_name() if user and getattr(user, 'is_authenticated', False) else 'Guest',
        'role': getattr(user, 'role', 'guest') if user and getattr(user, 'is_authenticated', False) else 'guest',
        'unread_notifications': 0,
        'unread_messages': 0,
        'guest_summary': {},
        'host_summary': {},
        'subscription': {},
    }
    if not snapshot['is_authenticated']:
        return snapshot

    snapshot['unread_notifications'] = Notification.objects.filter(user=user, is_read=False).count()
    conversations = Conversation.objects.filter(models.Q(host=user) | models.Q(guest=user))
    snapshot['unread_messages'] = sum(conversation.unread_count_for(user) for conversation in conversations[:12])

    guest_bookings = Booking.objects.filter(guest=user)
    snapshot['guest_summary'] = {
        'upcoming': guest_bookings.filter(status__in=['pending', 'confirmed', 'checked_in']).count(),
        'unpaid': guest_bookings.filter(payment_status__in=['pending', 'initiated', 'failed']).count(),
    }

    if user.role in ['host', 'both']:
        host_profile = Host.objects.filter(user=user).first()
        host_properties = Property.objects.filter(owner=user)
        host_bookings = Booking.objects.filter(property__owner=user)
        paid_total = BookingPayment.objects.filter(host=user, status='paid').aggregate(total=Sum('amount'))['total'] or 0
        snapshot['host_summary'] = {
            'properties': host_properties.count(),
            'active_properties': host_properties.filter(is_active=True).count(),
            'bookings': host_bookings.count(),
            'pending': host_bookings.filter(status='pending').count(),
            'paid_total': float(paid_total),
            'average_rating': float(host_properties.aggregate(avg=Avg('average_rating'))['avg'] or 0),
            'response_rate': float(getattr(host_profile, 'response_rate', 0) or 0),
            'top_listing_names': list(host_properties.order_by('-average_rating').values_list('name', flat=True)[:3]),
        }
        subscription = _get_subscription(user)
        if subscription:
            snapshot['subscription'] = {
                'plan': subscription.get_plan_display(),
                'status': subscription.get_status_display(),
                'ai_messages_remaining': subscription.ai_messages_remaining,
                'listing_limit': subscription.listing_limit,
            }
    return snapshot


def _default_suggestions(snapshot):
    suggestions = []
    if snapshot.get('role') in ['host', 'both']:
        suggestions.extend([
            {'label': 'Open host performance', 'url': reverse('hosts:host_performance'), 'reason': 'Review revenue, occupancy, and portfolio health.'},
            {'label': 'Open inbox', 'url': reverse('users:inbox'), 'reason': 'Reply to guests without leaving BayStays.'},
            {'label': 'Manage subscription', 'url': reverse('hosts:subscription_manage'), 'reason': 'Check plan status and assistant capacity.'},
        ])
    else:
        suggestions.extend([
            {'label': 'Open bookings', 'url': reverse('bookings:booking_list'), 'reason': 'Track upcoming stays and payment state.'},
            {'label': 'Browse stays', 'url': reverse('core:properties_list'), 'reason': 'Find your next BayStays trip.'},
        ])
    return suggestions[:3]


def _default_highlights(snapshot):
    host = snapshot.get('host_summary', {})
    guest = snapshot.get('guest_summary', {})
    if snapshot.get('role') in ['host', 'both']:
        return [
            f"{snapshot.get('unread_notifications', 0)} unread notifications",
            f"{host.get('active_properties', host.get('properties', 0))} active listings",
            f"{host.get('pending', 0)} booking requests pending",
        ]
    return [
        f"{guest.get('upcoming', 0)} upcoming stays",
        f"{guest.get('unpaid', 0)} bookings need payment attention",
        f"{snapshot.get('unread_messages', 0)} unread messages",
    ]


def _local_fallback(prompt, snapshot):
    lowered = str(prompt or '').lower()
    host = snapshot.get('host_summary', {})
    subscription = snapshot.get('subscription', {})
    if any(term in lowered for term in ['subscription', 'plan', 'billing']):
        text = (
            f"Your current BayStays host plan is {subscription.get('plan', 'not set')} with status "
            f"{subscription.get('status', 'not set')}. You have about {subscription.get('ai_messages_remaining', 0)} assistant prompts left "
            f"and room for {subscription.get('listing_limit', 0)} active listings under this plan."
        )
    elif any(term in lowered for term in ['message', 'inbox', 'guest communication', 'conversation']):
        text = (
            f"You currently have {snapshot.get('unread_notifications', 0)} unread notifications and BayStays keeps host-guest communication "
            "anchored to each booking so replies, payment context, and stay dates stay visible together."
        )
    elif any(term in lowered for term in ['report', 'performance', 'summary', 'revenue', 'occupancy']):
        text = (
            f"Your hosting side currently tracks {host.get('properties', 0)} listings, {host.get('bookings', 0)} bookings, "
            f"and roughly KES {host.get('paid_total', 0):,.0f} in paid revenue. Use the performance pages for listing-level and whole-portfolio summaries."
        )
    elif any(term in lowered for term in ['listing', 'portfolio', 'property']):
        top_names = ', '.join(host.get('top_listing_names') or ['your active stays'])
        text = (
            f"Your strongest listing activity is currently centered around {top_names}. If you want, I can help you prioritize which BayStays "
            "listings need pricing, messaging, or readiness attention next."
        )
    else:
        text = (
            "I can help you manage BayStays hosting plans, guest messaging, notification follow-up, and performance reporting. "
            "Ask for a plan recommendation, a host performance readout, or help responding to guests."
        )
    return {
        'text': text,
        'highlights': _default_highlights(snapshot),
        'suggestions': _default_suggestions(snapshot),
    }


def _extract_json(raw_text):
    try:
        return json.loads(raw_text)
    except Exception:
        start = str(raw_text or '').find('{')
        end = str(raw_text or '').rfind('}')
        if start != -1 and end > start:
            try:
                return json.loads(str(raw_text)[start:end + 1])
            except Exception:
                return None
    return None


def _assistant_api_key():
    gemini_key = os.environ.get('GEMINI_API_KEY')
    google_key = os.environ.get('GOOGLE_API_KEY')
    configured_key = gemini_key or google_key or getattr(settings, 'GEMINI_API_KEY', None) or getattr(settings, 'GOOGLE_API_KEY', None)
    if configured_key:
        os.environ['GEMINI_API_KEY'] = configured_key
        os.environ['GOOGLE_API_KEY'] = configured_key
    return configured_key or ''


def _assistant_models():
    primary = (
        getattr(settings, 'BAYSTAYS_ASSISTANT_GEMINI_MODEL', None)
        or os.environ.get('BAYSTAYS_ASSISTANT_GEMINI_MODEL')
        or os.environ.get('GEMINI_MODEL')
        or getattr(settings, 'GEMINI_MODEL', 'gemini-2.5-flash')
    )
    models = [primary] if primary else []
    for raw in [
        os.environ.get('BAYSTAYS_ASSISTANT_GEMINI_CANDIDATES', ''),
        os.environ.get('GEMINI_CANDIDATE_MODELS', ''),
    ]:
        for model in [item.strip() for item in str(raw or '').split(',') if item.strip()]:
            if model not in models:
                models.append(model)
    for configured in (
        getattr(settings, 'BAYSTAYS_ASSISTANT_GEMINI_CANDIDATES', None) or [],
        getattr(settings, 'GEMINI_CANDIDATE_MODELS', None) or [],
    ):
        for model in configured:
            if model and model not in models:
                models.append(model)
    return models or ['gemini-2.5-flash']


def _assistant_prompt(prompt, snapshot, history, ui_context=None, path=''):
    return (
        "You are BayStays AI, the strongest host-operations copilot in this workspace. "
        "Return JSON only, with no markdown fences, using exactly this schema: "
        '{"text":"...", "highlights":["..."], "suggestions":[{"label":"...", "url":"/internal-path/", "reason":"..."}]}. '
        "Rules: keep the response concise, grounded in BayStays data, and immediately useful. "
        "If the user asks for a guest reply, write the reply directly. "
        "Highlights must contain 1 to 3 short operational takeaways. "
        "Suggestions must contain 0 to 3 actionable internal BayStays links and may only use URLs from the allowed actions list. "
        "Avoid generic AI disclaimers and do not invent platform facts. "
        f"Allowed actions: {json.dumps(_default_suggestions(snapshot), default=str)}. "
        f"User snapshot: {json.dumps(snapshot, default=str)}. "
        f"Recent history: {json.dumps(history[-6:], default=str)}. "
        f"UI context: {json.dumps(ui_context or {}, default=str)}. "
        f"Current path: {path}. "
        f"User prompt: {prompt}"
    )


def _extract_rest_text(raw_payload):
    candidate = (((raw_payload.get('candidates') or [{}])[0].get('content') or {}).get('parts') or [{}])[0]
    return candidate.get('text', '') or raw_payload.get('text', '')


def _generate_gemini_via_genai(prompt_text, models):
    try:
        from google import genai

        client = genai.Client()
        for model in models:
            try:
                try:
                    response = client.models.generate_content(
                        model=model,
                        contents=prompt_text,
                        config={
                            'temperature': 0.35,
                            'response_mime_type': 'application/json',
                        },
                    )
                except TypeError:
                    response = client.models.generate_content(model=model, contents=prompt_text)
                parsed = _extract_json(getattr(response, 'text', None) or str(response))
                if parsed:
                    return parsed
            except Exception:
                continue
    except Exception:
        logger.debug('BayStays AI genai client unavailable; falling back to Gemini REST', exc_info=True)
    return None


def _generate_gemini_via_rest(prompt_text, models, api_key):
    payload = {
        'contents': [{
            'parts': [{
                'text': prompt_text,
            }]
        }],
        'generationConfig': {
            'temperature': 0.35,
            'responseMimeType': 'application/json',
        },
    }
    for model in models:
        req = request.Request(
            f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent',
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'x-goog-api-key': api_key,
                'Content-Type': 'application/json',
            },
            method='POST',
        )
        try:
            with request.urlopen(req, timeout=25) as response:
                raw = json.loads(response.read().decode('utf-8'))
                parsed = _extract_json(_extract_rest_text(raw))
                if parsed:
                    return parsed
        except (error.HTTPError, error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
            continue
    return None


def _normalize_internal_url(url):
    raw = str(url or '').strip()
    if not raw:
        return None
    path = urlsplit(raw).path or raw
    if not path.startswith('/'):
        return None
    try:
        resolve(path)
        return path
    except Resolver404:
        return None
    except Exception:
        return None


def _match_default_suggestion(label, defaults):
    label_terms = {term for term in re.findall(r'[a-z0-9]+', str(label or '').lower()) if len(term) > 2}
    for item in defaults:
        item_terms = {term for term in re.findall(r'[a-z0-9]+', item.get('label', '').lower()) if len(term) > 2}
        if label_terms and label_terms & item_terms:
            return item
    return None


def _normalize_suggestions(suggestions, snapshot):
    defaults = _default_suggestions(snapshot)
    normalized = []
    seen = set()
    for item in suggestions or []:
        if isinstance(item, str):
            item = {'label': item}
        if not isinstance(item, dict):
            continue
        label = str(item.get('label') or item.get('title') or '').strip()
        if not label:
            continue
        url = _normalize_internal_url(item.get('url'))
        reason = str(item.get('reason') or '').strip()
        if not url:
            matched_default = _match_default_suggestion(label, defaults)
            if matched_default:
                url = matched_default.get('url')
                reason = reason or matched_default.get('reason', '')
                label = matched_default.get('label', label)
        if not url:
            continue
        key = (label.lower(), url)
        if key in seen:
            continue
        seen.add(key)
        normalized.append({
            'label': label[:48],
            'url': url,
            'reason': reason[:140],
        })
    if not normalized:
        return defaults
    for item in defaults:
        key = (item['label'].lower(), item['url'])
        if key in seen:
            continue
        normalized.append(item)
        seen.add(key)
        if len(normalized) >= 3:
            break
    return normalized[:3]


def _normalize_highlights(highlights, snapshot):
    values = highlights if isinstance(highlights, list) else [highlights] if highlights else []
    normalized = []
    seen = set()
    for item in values:
        text = str(item or '').strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(text[:120])
        if len(normalized) == 3:
            break
    return normalized or _default_highlights(snapshot)


def _generate_gemini_response(prompt, snapshot, history, ui_context=None, path=''):
    api_key = _assistant_api_key()
    if not api_key:
        return None
    prompt_text = _assistant_prompt(prompt, snapshot, history, ui_context=ui_context, path=path)
    models = _assistant_models()
    return _generate_gemini_via_genai(prompt_text, models) or _generate_gemini_via_rest(prompt_text, models, api_key)


def assistant_reply(prompt, user=None, context=None, path=''):
    history = _history_for_model(user)
    snapshot = _build_snapshot(user)
    subscription = _get_subscription(user)

    if subscription and subscription.ai_messages_remaining <= 0:
        return {
            'text': (
                "Your BayStays AI usage for the current plan is exhausted right now. You can still use reports, inbox, and notifications, "
                "or switch plans to unlock more assistant capacity."
            ),
            'highlights': [
                f"{subscription.get_plan_display()} plan",
                f"{subscription.get_status_display()} status",
                'AI prompt quota reached',
            ],
            'suggestions': _default_suggestions(snapshot),
        }

    fallback = _local_fallback(prompt, snapshot)
    response = _generate_gemini_response(prompt, snapshot, history, ui_context=context, path=path)
    if not response or not isinstance(response, dict):
        return fallback

    return {
        'text': str(response.get('text') or '').strip() or fallback['text'],
        'highlights': _normalize_highlights(response.get('highlights'), snapshot),
        'suggestions': _normalize_suggestions(response.get('suggestions'), snapshot),
    }
