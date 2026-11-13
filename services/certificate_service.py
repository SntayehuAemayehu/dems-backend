# backend/services/certificate_service.py
# COMPLETE CERTIFICATE GENERATION SYSTEM

from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from io import BytesIO
from django.core.files.base import ContentFile
from courses.models import Enrollment
from django.utils import timezone
from django.conf import settings
from utils.grading import calculate_grade, calculate_grade_from_mark
import hashlib
import html
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class CertificateService:
    """Professional certificate generation with verification"""

    def _grade_calculation(self, enrollment):
        if enrollment.total_marks_obtained is not None and enrollment.total_marks_possible:
            return calculate_grade_from_mark(
                float(enrollment.total_marks_obtained),
                float(enrollment.total_marks_possible),
            )
        return calculate_grade(enrollment.percentage_score)

    def _weighted_gpa(self, enrollments):
        total_points = 0.0
        total_credits = 0
        for item in enrollments:
            credits = item.course.credit_hours or 0
            if credits > 0:
                total_points += self._grade_calculation(item)['gpa'] * credits
                total_credits += credits
        return round(total_points / total_credits, 2) if total_credits else None

    def generate_course_certificate(self, student, enrollment):
        """Generate a transcript listing all courses enrolled by the student."""
        from certificates.models import Certificate

        published_ids = set(Certificate.objects.filter(
            student=student,
            is_published=True,
        ).values_list('enrollment_id', flat=True))
        published_ids.add(enrollment.id)
        enrollments = list(Enrollment.objects.filter(
            student=student,
        ).select_related('course').order_by(
            'course__year',
            'course__semester',
            'course__course_code',
        ))
        released_enrollments = [
            item for item in enrollments
            if item.id in published_ids
            and item.status == 'COMPLETED'
            and item.result_sent_to_registrar
        ]
        semester = str(student.current_semester).strip()
        semester_gpa = self._weighted_gpa([
            item for item in released_enrollments
            if str(item.course.semester).strip() == semester
        ])
        cgpa = self._weighted_gpa(released_enrollments)

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
        story.append(Paragraph('OFFICIAL ACADEMIC TRANSCRIPT', title_style))
        story.append(Paragraph('Academic record for', body_style))
        story.append(Paragraph(html.escape(student.user.full_name), name_style))
        detail_style = ParagraphStyle(
            name='CertificateStudentDetails',
            parent=styles['Normal'],
            fontSize=9,
            leading=12,
            textColor=navy,
        )
        student_year = student.year or (
            (student.current_semester + 1) // 2 if student.current_semester else 0
        )
        detail_table = Table([[
            Paragraph(f'<b>STUDENT ID</b><br/>{html.escape(student.student_id or "N/A")}', detail_style),
            Paragraph(f'<b>ACADEMIC YEAR</b><br/>Year {student_year or "N/A"}', detail_style),
            Paragraph(f'<b>SEMESTER</b><br/>{student.current_semester or "N/A"}', detail_style),
        ]], colWidths=[3.05*inch] * 3)
        detail_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
            ('BOX', (0, 0), (-1, -1), 0.8, gold),
            ('INNERGRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#e2e8f0')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ]))
        story.append(detail_table)
        story.append(Spacer(1, 12))

        table_style = ParagraphStyle(
            name='CertificateTableText',
            parent=styles['Normal'],
            fontSize=8,
            leading=10,
            textColor=navy,
        )
        table_header_style = ParagraphStyle(
            name='CertificateTableHeader',
            parent=table_style,
            fontName='Helvetica-Bold',
            fontSize=7,
            leading=9,
            alignment=1,
            textColor=colors.white,
        )
        course_rows = [[
            Paragraph(label, table_header_style)
            for label in ('COURSE ID', 'COURSE NAME', 'YEAR', 'SEMESTER', 'SCORE', 'GRADE', 'GPA')
        ]]
        for item in enrollments:
            released = (
                item.id in published_ids
                and item.status == 'COMPLETED'
                and item.result_sent_to_registrar
            )
            calculation = self._grade_calculation(item) if released else None
            score = 'Not issued'
            if released and item.total_marks_obtained is not None:
                score = f'{float(item.total_marks_obtained):.2f}'
                if item.total_marks_possible is not None:
                    score += f' / {float(item.total_marks_possible):.2f}'
            course_rows.append([
                Paragraph(html.escape(item.course.course_code), table_style),
                Paragraph(html.escape(item.course.title), table_style),
                str(item.course.year or 'N/A'),
                str(item.course.semester or 'N/A'),
                score,
                calculation['letter'] if calculation else 'Not issued',
                f'{calculation["gpa"]:.2f}' if calculation else 'Not issued',
            ])

        courses_table = Table(
            course_rows,
            colWidths=[1.05*inch, 3.3*inch, 0.65*inch, 0.8*inch, 1.5*inch, 0.65*inch, 0.75*inch],
            repeatRows=1,
        )
        courses_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), navy),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#faf8f0')]),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#d9dee7')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (2, 1), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(courses_table)
        story.append(Spacer(1, 11))

        summary_style = ParagraphStyle(
            name='CertificateGpaSummary',
            parent=styles['Normal'],
            fontName='Helvetica-Bold',
            fontSize=11,
            leading=15,
            alignment=1,
            textColor=navy,
        )
        summary_table = Table([[
            Paragraph(
                f'SEMESTER GPA<br/>{semester_gpa:.2f}' if semester_gpa is not None else 'SEMESTER GPA<br/>N/A',
                summary_style,
            ),
            Paragraph(
                f'CUMULATIVE GPA<br/>{cgpa:.2f}' if cgpa is not None else 'CUMULATIVE GPA<br/>N/A',
                summary_style,
            ),
        ]], colWidths=[4.275*inch, 4.275*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
            ('BOX', (0, 0), (-1, -1), 0.8, gold),
            ('INNERGRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#e2e8f0')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 9))

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