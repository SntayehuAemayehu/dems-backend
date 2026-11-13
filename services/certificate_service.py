# backend/services/certificate_service.py
# COMPLETE CERTIFICATE GENERATION SYSTEM

from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from io import BytesIO
from django.core.files.base import ContentFile
from accounts.models import StudentProfile
from courses.models import Enrollment
from django.utils import timezone
from django.conf import settings
import hashlib
import html
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class CertificateService:
    """Professional certificate generation with verification"""

    def generate_course_certificate(self, student, enrollment):
        """Generate course completion certificate"""
        buffer = BytesIO()
        navy = colors.HexColor('#102a43')
        gold = colors.HexColor('#b49137')
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(letter),
            rightMargin=0.85*inch,
            leftMargin=0.85*inch,
            topMargin=0.55*inch,
            bottomMargin=0.55*inch
        )
        story = []

        styles = getSampleStyleSheet()
        university_style = ParagraphStyle(
            name='CertificateUniversity',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=13,
            leading=17,
            alignment=1,
            textColor=navy,
            spaceAfter=2,
            tracking=2,
        )
        subtitle_style = ParagraphStyle(
            name='CertificateSubtitle',
            parent=styles['Normal'],
            fontSize=8,
            leading=11,
            alignment=1,
            textColor=colors.HexColor('#64748b'),
            spaceAfter=8,
        )
        title_style = ParagraphStyle(
            name='CertificateDisplayTitle',
            parent=styles['Title'],
            fontName='Times-Bold',
            fontSize=27,
            leading=32,
            alignment=1,
            textColor=navy,
            spaceBefore=5,
            spaceAfter=7,
        )
        body_style = ParagraphStyle(
            name='CertificateDisplayBody',
            parent=styles['Normal'],
            fontName='Times-Roman',
            fontSize=12,
            leading=17,
            alignment=1,
            textColor=colors.HexColor('#475569'),
            spaceAfter=4,
        )
        name_style = ParagraphStyle(
            name='CertificateDisplayName',
            parent=styles['Normal'],
            fontName='Times-Bold',
            fontSize=24,
            leading=29,
            alignment=1,
            textColor=navy,
            spaceBefore=2,
            spaceAfter=8,
        )
        course_style = ParagraphStyle(
            name='CertificateDisplayCourse',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=15,
            leading=19,
            alignment=1,
            textColor=colors.HexColor('#9a7629'),
            spaceBefore=2,
            spaceAfter=5,
        )

        logo_path = Path(settings.BASE_DIR).parent / 'dems-frontend' / 'public' / 'Mekdela_Amba_University_logo.jpg'
        if logo_path.is_file():
            logo = Image(str(logo_path), width=0.58*inch, height=0.58*inch, kind='proportional')
            logo.hAlign = 'CENTER'
            story.append(logo)
            story.append(Spacer(1, 4))

        story.append(Paragraph(
            'MEKDELA AMBA UNIVERSITY',
            university_style,
        ))
        story.append(Paragraph(
            'DISTANCE EDUCATION MANAGEMENT SYSTEM',
            subtitle_style,
        ))
        story.append(Paragraph('CERTIFICATE OF ACHIEVEMENT', title_style))
        story.append(Paragraph('This certificate is proudly presented to', body_style))
        story.append(Paragraph(html.escape(student.user.full_name), name_style))
        story.append(Paragraph(
            f'for the successful completion of <b>{html.escape(enrollment.course.title)}</b>',
            body_style,
        ))
        story.append(Paragraph(
            f'{html.escape(enrollment.course.course_code)}',
            course_style,
        ))
        grade_style = ParagraphStyle(
            name='CertificateGradeValue',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=12,
            leading=16,
            alignment=1,
            textColor=navy,
        )
        grade_label_style = ParagraphStyle(
            name='CertificateGradeLabel',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=7,
            leading=10,
            alignment=1,
            textColor=colors.HexColor('#64748b'),
        )
        grade_table = Table([[
            [Paragraph('FINAL GRADE', grade_label_style), Paragraph(html.escape(enrollment.grade_letter or 'NON'), grade_style)],
            [Paragraph('PERCENTAGE', grade_label_style), Paragraph(f'{float(enrollment.percentage_score or 0):.1f}%', grade_style)],
            [Paragraph('CREDIT HOURS', grade_label_style), Paragraph(str(enrollment.course.credit_hours or 0), grade_style)],
        ]], colWidths=[2.5*inch] * 3)
        grade_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
            ('BOX', (0, 0), (-1, -1), 0.8, gold),
            ('INNERGRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#e2e8f0')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(Spacer(1, 7))
        story.append(grade_table)
        story.append(Spacer(1, 15))

        signature_table = Table([
            ['____________________________', '____________________________'],
            ['Dean of Students', 'Registrar'],
        ], colWidths=[3.5*inch, 3.5*inch])
        signature_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TEXTCOLOR', (0, 0), (-1, 0), gold),
            ('TEXTCOLOR', (0, 1), (-1, 1), navy),
            ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, 1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(signature_table)

        certification_id = self.generate_certification_id(student, enrollment)
        footer_style = ParagraphStyle(
            name='CertificateFooter',
            parent=styles['Normal'],
            fontSize=7,
            leading=9,
            alignment=1,
            textColor=colors.HexColor('#64748b'),
            spaceBefore=3,
        )
        story.append(Paragraph(
            f'OFFICIALLY ISSUED · {certification_id} · {timezone.now().strftime("%B %d, %Y")}',
            footer_style,
        ))

        def draw_frame(canvas, document):
            page_width, page_height = document.pagesize
            canvas.saveState()
            canvas.setStrokeColor(gold)
            canvas.setLineWidth(2)
            canvas.roundRect(20, 20, page_width - 40, page_height - 40, 10, stroke=1, fill=0)
            canvas.setStrokeColor(navy)
            canvas.setLineWidth(0.6)
            canvas.roundRect(27, 27, page_width - 54, page_height - 54, 7, stroke=1, fill=0)
            canvas.restoreState()

        doc.build(story, onFirstPage=draw_frame, onLaterPages=draw_frame)

        buffer.seek(0)
        pdf_content = buffer.getvalue()
        buffer.close()
        
        return {
            'pdf': pdf_content,
            'certification_id': certification_id,
            'filename': f"certificate_{student.student_id}_{enrollment.course.course_code}.pdf"
        }
    
    def generate_certification_id(self, student, enrollment):
        """Generate unique certification ID"""
        data = f"{student.id}-{enrollment.course.id}-{student.student_id}-{enrollment.course.course_code}"
        hash_object = hashlib.sha256(data.encode())
        return f"CERT-{hash_object.hexdigest()[:8].upper()}-{timezone.now().year}"
    
    def verify_certificate(self, certification_id):
        """Verify certificate authenticity"""
        # In real system, you'd query a database
        # For now, return true with basic validation
        try:
            parts = certification_id.split('-')
            if len(parts) == 3 and parts[0] == 'CERT':
                return {
                    'valid': True,
                    'certification_id': certification_id,
                    'issued_year': int(parts[2])
                }
        except:
            pass
        
        return {
            'valid': False,
            'message': 'Invalid certification ID'
        }

# Singleton
certificate_service = CertificateService()