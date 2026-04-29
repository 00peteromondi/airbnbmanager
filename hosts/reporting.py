from datetime import timedelta
from decimal import Decimal
from io import BytesIO

from django.db.models import Avg, Count, Sum
from django.db.models.functions import TruncMonth
from django.http import HttpResponse
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from bookings.models import Booking, BookingPayment
from properties.models import Property


def _coalesce_decimal(value):
    return value or Decimal('0.00')


def _month_buckets():
    today = timezone.localdate().replace(day=1)
    buckets = []
    year = today.year
    month = today.month
    for offset in range(5, -1, -1):
        bucket_month = month - offset
        bucket_year = year
        while bucket_month <= 0:
            bucket_month += 12
            bucket_year -= 1
        buckets.append(today.replace(year=bucket_year, month=bucket_month, day=1))
    return buckets


def _fill_month_series(raw_rows, revenue_key='revenue', count_key='count'):
    mapping = {row['month'].date().replace(day=1): row for row in raw_rows}
    series = []
    for bucket in _month_buckets():
        row = mapping.get(bucket)
        series.append({
            'label': bucket.strftime('%b'),
            'revenue': float(row.get(revenue_key) or 0) if row else 0,
            'count': int(row.get(count_key) or 0) if row else 0,
        })
    max_revenue = max([item['revenue'] for item in series] or [0]) or 1
    for item in series:
        item['revenue_ratio'] = max(item['revenue'] / max_revenue, 0)
        item['revenue_percent'] = round(item['revenue_ratio'] * 100)
    return series


def build_listing_report(property_obj):
    bookings = Booking.objects.filter(property=property_obj).select_related('guest')
    paid_payments = BookingPayment.objects.filter(booking__property=property_obj, status='paid')
    total_bookings = bookings.count()
    completed_count = bookings.filter(status__in=['completed', 'checked_out']).count()
    cancelled_count = bookings.filter(status='cancelled').count()
    confirmed_count = bookings.filter(status__in=['confirmed', 'checked_in']).count()
    gross_revenue = _coalesce_decimal(bookings.filter(status__in=Booking.REVENUE_ACTIVE_STATUSES).aggregate(total=Sum('total_price'))['total'])
    paid_revenue = _coalesce_decimal(paid_payments.aggregate(total=Sum('amount'))['total'])
    average_stay_length = 0
    if total_bookings:
        total_nights = sum(max((booking.check_out_date - booking.check_in_date).days, 0) for booking in bookings)
        average_stay_length = round(total_nights / max(total_bookings, 1), 1)

    monthly_rows = list(
        bookings.annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(count=Count('id'), revenue=Sum('total_price'))
        .order_by('month')
    )
    trend = _fill_month_series(monthly_rows)
    occupancy_rate = 0
    window_start = timezone.localdate() - timedelta(days=90)
    occupancy_nights = sum(
        max((min(booking.check_out_date, timezone.localdate()) - max(booking.check_in_date, window_start)).days, 0)
        for booking in bookings.filter(status__in=Booking.REVENUE_ACTIVE_STATUSES, check_out_date__gte=window_start)
    )
    occupancy_rate = round(min((occupancy_nights / 90) * 100, 100), 1) if occupancy_nights else 0

    recommendations = []
    if property_obj.images.count() < 5:
        recommendations.append('Add more gallery photos to improve guest confidence before booking.')
    if occupancy_rate < 35:
        recommendations.append('Occupancy is soft over the last 90 days. Revisit pricing, stay details, and guest messaging speed.')
    if cancelled_count > completed_count:
        recommendations.append('Cancellations are outweighing completed stays. Review guest communication and listing clarity.')
    if not recommendations:
        recommendations.append('This listing is performing steadily. Keep response time and photo freshness high.')

    return {
        'property': property_obj,
        'metrics': {
            'total_bookings': total_bookings,
            'confirmed_count': confirmed_count,
            'completed_count': completed_count,
            'cancelled_count': cancelled_count,
            'gross_revenue': gross_revenue,
            'paid_revenue': paid_revenue,
            'average_stay_length': average_stay_length,
            'occupancy_rate': occupancy_rate,
            'average_rating': property_obj.average_rating,
            'image_count': property_obj.images.count(),
        },
        'trend': trend,
        'recommendations': recommendations,
        'recent_bookings': bookings.order_by('-created_at')[:6],
    }


def build_host_report(user):
    properties = Property.objects.filter(owner=user).prefetch_related('images')
    bookings = Booking.objects.filter(property__owner=user).select_related('property', 'guest')
    payments = BookingPayment.objects.filter(host=user, status='paid')
    monthly_rows = list(
        bookings.annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(count=Count('id'), revenue=Sum('total_price'))
        .order_by('month')
    )
    trend = _fill_month_series(monthly_rows)
    listing_reports = [build_listing_report(property_obj) for property_obj in properties[:8]]
    portfolio_revenue = _coalesce_decimal(bookings.filter(status__in=Booking.REVENUE_ACTIVE_STATUSES).aggregate(total=Sum('total_price'))['total'])
    paid_revenue = _coalesce_decimal(payments.aggregate(total=Sum('amount'))['total'])
    average_rating = properties.aggregate(avg=Avg('average_rating'))['avg'] or 0
    active_listings = properties.filter(is_active=True).count()
    pending_count = bookings.filter(status='pending').count()

    recommendations = []
    if properties.count() == 0:
        recommendations.append('Create your first BayStays listing to start building portfolio momentum.')
    if pending_count > 4:
        recommendations.append('Clear the pending approvals queue faster so high-intent guests do not cool off.')
    if active_listings < properties.count():
        recommendations.append('You have paused listings that may be limiting portfolio revenue.')
    if average_rating and average_rating < 4.5:
        recommendations.append('Average rating is below superhost territory. Review post-stay feedback and listing expectations.')
    if not recommendations:
        recommendations.append('Your host portfolio is healthy. Focus next on repeatable guest communication and pricing discipline.')

    return {
        'user': user,
        'properties': properties,
        'listing_reports': listing_reports,
        'metrics': {
            'properties_count': properties.count(),
            'active_listings': active_listings,
            'bookings_count': bookings.count(),
            'pending_count': pending_count,
            'completed_count': bookings.filter(status__in=['completed', 'checked_out']).count(),
            'gross_revenue': portfolio_revenue,
            'paid_revenue': paid_revenue,
            'average_rating': average_rating,
        },
        'trend': trend,
        'recommendations': recommendations,
        'recent_payments': payments.order_by('-created_at')[:6],
    }


def build_pdf_response(filename, title, subtitle, sections):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )
    palette = {
        'primary': colors.HexColor('#cf2338'),
        'primary_dark': colors.HexColor('#7f1022'),
        'soft': colors.HexColor('#fff4ef'),
        'line': colors.HexColor('#e2e8f0'),
        'text': colors.HexColor('#1f2937'),
        'muted': colors.HexColor('#64748b'),
    }
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='BayTitle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=22, leading=27, textColor=colors.white, alignment=TA_LEFT))
    styles.add(ParagraphStyle(name='BaySubtitle', parent=styles['BodyText'], fontName='Helvetica', fontSize=10.2, leading=14, textColor=colors.white))
    styles.add(ParagraphStyle(name='BaySection', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=12, leading=16, textColor=palette['primary_dark']))
    styles.add(ParagraphStyle(name='BayBody', parent=styles['BodyText'], fontName='Helvetica', fontSize=10.2, leading=14.5, textColor=palette['text']))
    styles.add(ParagraphStyle(name='BayMeta', parent=styles['BodyText'], fontName='Helvetica', fontSize=9.2, leading=13, textColor=palette['muted']))

    story = []
    header = Table([[Paragraph(f'BayStays<br/><font size="10">{title}</font>', styles['BayTitle']), Paragraph(subtitle, styles['BaySubtitle'])]], colWidths=[108 * mm, 58 * mm])
    header.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), palette['primary']),
        ('LEFTPADDING', (0, 0), (-1, -1), 16),
        ('RIGHTPADDING', (0, 0), (-1, -1), 16),
        ('TOPPADDING', (0, 0), (-1, -1), 14),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 16),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(header)
    story.append(Spacer(1, 10))

    for section in sections:
        story.append(Paragraph(section['heading'], styles['BaySection']))
        story.append(Spacer(1, 4))
        if section.get('intro'):
            story.append(Paragraph(section['intro'], styles['BayBody']))
            story.append(Spacer(1, 6))
        if section.get('rows'):
            data = [
                [Paragraph(f"<b>{label}</b>", styles['BayMeta']), Paragraph(str(value), styles['BayBody'])]
                for label, value in section['rows']
            ]
            table = Table(data, colWidths=[50 * mm, 116 * mm])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), palette['soft']),
                ('BOX', (0, 0), (-1, -1), 0.6, palette['line']),
                ('INNERGRID', (0, 0), (-1, -1), 0.6, palette['line']),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            story.append(table)
            story.append(Spacer(1, 8))
        if section.get('notes'):
            for note in section['notes']:
                note_table = Table([[Paragraph(note, styles['BayBody'])]], colWidths=[166 * mm])
                note_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fef3c7')),
                    ('BOX', (0, 0), (-1, -1), 0.6, colors.HexColor('#f59e0b')),
                    ('LEFTPADDING', (0, 0), (-1, -1), 10),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                    ('TOPPADDING', (0, 0), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ]))
                story.append(note_table)
                story.append(Spacer(1, 6))

    doc.build(story)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
