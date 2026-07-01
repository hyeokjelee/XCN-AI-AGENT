#!/usr/bin/env python3
"""Generate Kim Min-gi Security Comprehensive Analysis Report PDF"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, HRFlowable
)
from reportlab.platypus.doctemplate import BaseDocTemplate
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
import datetime

# Output path
OUTPUT_PATH = "/app/tmp/workspace/김민기_보안종합분석보고서_20260611.pdf"

# Colors
DARK_BLUE = HexColor("#1a365d")
MEDIUM_BLUE = HexColor("#2b6cb0")
LIGHT_BLUE = HexColor("#ebf4ff")
ACCENT_BLUE = HexColor("#3182ce")
DARK_GRAY = HexColor("#2d3748")
MEDIUM_GRAY = HexColor("#4a5568")
LIGHT_GRAY = HexColor("#e2e8f0")
VERY_LIGHT_GRAY = HexColor("#f7fafc")
WHITE = white
RED_ACCENT = HexColor("#e53e3e")
AMBER = HexColor("#d69e2e")
GREEN = HexColor("#38a169")

PAGE_WIDTH, PAGE_HEIGHT = A4
LEFT_MARGIN = 2.0 * cm
RIGHT_MARGIN = 2.0 * cm
CONTENT_WIDTH = PAGE_WIDTH - LEFT_MARGIN - RIGHT_MARGIN

# Custom styles
styles = getSampleStyleSheet()

title_style = ParagraphStyle(
    'ReportTitle', parent=styles['Title'],
    fontSize=28, textColor=DARK_BLUE, spaceAfter=6*mm,
    fontName='Helvetica-Bold', alignment=TA_CENTER, leading=36
)

subtitle_style = ParagraphStyle(
    'ReportSubtitle', parent=styles['Normal'],
    fontSize=14, textColor=MEDIUM_BLUE, spaceAfter=3*mm,
    fontName='Helvetica', alignment=TA_CENTER, leading=20
)

date_style = ParagraphStyle(
    'ReportDate', parent=styles['Normal'],
    fontSize=11, textColor=MEDIUM_GRAY, spaceAfter=3*mm,
    fontName='Helvetica', alignment=TA_CENTER, leading=16
)

author_style = ParagraphStyle(
    'ReportAuthor', parent=styles['Normal'],
    fontSize=12, textColor=DARK_GRAY, spaceAfter=6*mm,
    fontName='Helvetica', alignment=TA_CENTER, leading=18
)

section_title_style = ParagraphStyle(
    'SectionTitle', parent=styles['Heading1'],
    fontSize=16, textColor=DARK_BLUE, spaceBefore=8*mm, spaceAfter=4*mm,
    fontName='Helvetica-Bold', leading=22,
    borderWidth=0, borderPadding=0,
)

subsection_title_style = ParagraphStyle(
    'SubsectionTitle', parent=styles['Heading2'],
    fontSize=13, textColor=MEDIUM_BLUE, spaceBefore=6*mm, spaceAfter=3*mm,
    fontName='Helvetica-Bold', leading=18,
)

body_style = ParagraphStyle(
    'BodyText', parent=styles['Normal'],
    fontSize=10, textColor=DARK_GRAY, spaceBefore=2*mm, spaceAfter=2*mm,
    fontName='Helvetica', leading=15, alignment=TA_JUSTIFY
)

bullet_style = ParagraphStyle(
    'BulletText', parent=styles['Normal'],
    fontSize=10, textColor=DARK_GRAY, spaceBefore=1*mm, spaceAfter=1*mm,
    fontName='Helvetica', leading=14, leftIndent=12,
    bulletIndent=6, bulletFontName='Helvetica', bulletFontSize=10
)

bullet_style_deep = ParagraphStyle(
    'BulletTextDeep', parent=styles['Normal'],
    fontSize=9.5, textColor=MEDIUM_GRAY, spaceBefore=1*mm, spaceAfter=1*mm,
    fontName='Helvetica', leading=13, leftIndent=24,
    bulletIndent=18, bulletFontName='Helvetica', bulletFontSize=9
)

table_header_style = ParagraphStyle(
    'TableHeader', parent=styles['Normal'],
    fontSize=9, textColor=WHITE, fontName='Helvetica-Bold', leading=13
)

table_cell_style = ParagraphStyle(
    'TableCell', parent=styles['Normal'],
    fontSize=9, textColor=DARK_GRAY, fontName='Helvetica', leading=13
)

table_cell_style_bold = ParagraphStyle(
    'TableCellBold', parent=styles['Normal'],
    fontSize=9, textColor=DARK_GRAY, fontName='Helvetica-Bold', leading=13
)

warning_style = ParagraphStyle(
    'WarningText', parent=styles['Normal'],
    fontSize=10, textColor=RED_ACCENT, fontName='Helvetica', leading=15,
    spaceBefore=2*mm, spaceAfter=2*mm
)

highlight_style = ParagraphStyle(
    'HighlightText', parent=styles['Normal'],
    fontSize=10, textColor=DARK_BLUE, fontName='Helvetica-Bold', leading=15,
    spaceBefore=2*mm, spaceAfter=2*mm
)

footer_style = ParagraphStyle(
    'FooterText', parent=styles['Normal'],
    fontSize=8, textColor=MEDIUM_GRAY, fontName='Helvetica', leading=12,
    alignment=TA_CENTER
)

# Cover page
def cover_page(canvas_obj, doc):
    canvas_obj.saveState()
    # Background
    canvas_obj.setFillColor(LIGHT_BLUE)
    canvas_obj.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=1, stroke=0)
    # Top accent bar
    canvas_obj.setFillColor(DARK_BLUE)
    canvas_obj.rect(0, PAGE_HEIGHT - 8*mm, PAGE_WIDTH, 8*mm, fill=1, stroke=0)
    # Bottom accent bar
    canvas_obj.setFillColor(MEDIUM_BLUE)
    canvas_obj.rect(0, 0, PAGE_WIDTH, 3*mm, fill=1, stroke=0)
    # Title
    canvas_obj.setFont('Helvetica-Bold', 28)
    canvas_obj.setFillColor(DARK_BLUE)
    canvas_obj.drawCentredString(PAGE_WIDTH/2, PAGE_HEIGHT/2 + 40*mm, "김민기 대리 보안 종합 분석 보고서")
    # Subtitle
    canvas_obj.setFont('Helvetica', 16)
    canvas_obj.setFillColor(MEDIUM_BLUE)
    canvas_obj.drawCentredString(PAGE_WIDTH/2, PAGE_HEIGHT/2 + 15*mm, "2026년 4월 ~ 6월")
    # Date
    canvas_obj.setFont('Helvetica', 12)
    canvas_obj.setFillColor(MEDIUM_GRAY)
    canvas_obj.drawCentredString(PAGE_WIDTH/2, PAGE_HEIGHT/2 - 10*mm, "2026년 6월 11일")
    # Author
    canvas_obj.setFont('Helvetica-Bold', 13)
    canvas_obj.setFillColor(DARK_GRAY)
    canvas_obj.drawCentredString(PAGE_WIDTH/2, PAGE_HEIGHT/2 - 25*mm, "XCURENET 선행개발팀")
    # Classification
    canvas_obj.setFont('Helvetica', 10)
    canvas_obj.setFillColor(RED_ACCENT)
    canvas_obj.drawCentredString(PAGE_WIDTH/2, 15*mm, "⚠️ 내부 문서 - 기밀")
    canvas_obj.restoreState()

# Header and footer
def header_footer(canvas_obj, doc):
    canvas_obj.saveState()
    # Header line
    canvas_obj.setStrokeColor(LIGHT_GRAY)
    canvas_obj.setLineWidth(0.5)
    canvas_obj.line(LEFT_MARGIN, PAGE_HEIGHT - 15*mm, PAGE_WIDTH - RIGHT_MARGIN, PAGE_HEIGHT - 15*mm)
    # Header text
    canvas_obj.setFont('Helvetica', 8)
    canvas_obj.setFillColor(MEDIUM_GRAY)
    canvas_obj.drawString(LEFT_MARGIN, PAGE_HEIGHT - 13*mm, "김민기 대리 보안 종합 분석 보고서")
    # Footer
    canvas_obj.line(LEFT_MARGIN, 15*mm, PAGE_WIDTH - RIGHT_MARGIN, 15*mm)
    canvas_obj.setFont('Helvetica', 8)
    canvas_obj.setFillColor(MEDIUM_GRAY)
    canvas_obj.drawString(LEFT_MARGIN, 13*mm, "XCURENET 선행개발팀 | 내부 문서")
    canvas_obj.drawRightString(PAGE_WIDTH - RIGHT_MARGIN, 13*mm, f"Page {doc.page}")
    canvas_obj.restoreState()

# Build document
doc = SimpleDocTemplate(
    OUTPUT_PATH,
    pagesize=A4,
    leftMargin=LEFT_MARGIN,
    rightMargin=RIGHT_MARGIN,
    topMargin=20*mm,
    bottomMargin=20*mm,
    title="김민기 대리 보안 종합 분석 보고서",
    author="XCURENET 선행개발팀",
    subject="보안 종합 분석 보고서",
)

story = []

# ============ COVER PAGE ============
story.append(Spacer(1, 1*cm))
story.append(Paragraph("김민기 대리 보안 종합 분석 보고서", title_style))
story.append(Paragraph("2026년 4월 ~ 6월", subtitle_style))
story.append(Spacer(1, 5*mm))
story.append(Paragraph("2026년 6월 11일", date_style))
story.append(Paragraph("XCURENET 선행개발팀", author_style))
story.append(Spacer(1, 2*cm))

# Summary box on cover
summary_data = [
    [Paragraph("📊 분석 요약", ParagraphStyle('SummaryHeader', parent=styles['Normal'], fontSize=11, textColor=DARK_BLUE, fontName='Helvetica-Bold'))],
    [Paragraph("• 총 2,771건의 로깅 데이터 분석", bullet_style)],
    [Paragraph("• 주요 활동: AI/ML 연구, 보안 솔루션 개발, 생성형 AI 활용", bullet_style)],
    [Paragraph("• 보안 위험도: 중간 (특이사항 4건 발견)", bullet_style)],
]
summary_table = Table(summary_data, colWidths=[CONTENT_WIDTH])
summary_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, -1), LIGHT_BLUE),
    ('BOX', (0, 0), (-1, -1), 1, MEDIUM_BLUE),
    ('TOPPADDING', (0, 0), (-1, -1), 6*mm),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 6*mm),
    ('LEFTPADDING', (0, 0), (-1, -1), 8*mm),
    ('RIGHTPADDING', (0, 0), (-1, -1), 8*mm),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
]))
story.append(summary_table)
story.append(PageBreak())

# ============ SECTION 1: BASIC INFO ============
story.append(Paragraph("1. 기본 정보", section_title_style))
story.append(HRFlowable(width="100%", thickness=1, color=MEDIUM_BLUE))

basic_info_data = [
    [Paragraph("항목", table_header_style), Paragraph("내용", table_header_style)],
    [Paragraph("성명", table_cell_style_bold), Paragraph("김민기", table_cell_style)],
    [Paragraph("직급", table_cell_style_bold), Paragraph("대리", table_cell_style)],
    [Paragraph("소속", table_cell_style_bold), Paragraph("선행개발팀", table_cell_style)],
    [Paragraph("이메일", table_cell_style_bold), Paragraph("mg.kim@xcurenet.com", table_cell_style)],
    [Paragraph("분석 기간", table_cell_style_bold), Paragraph("2026.04 ~ 2026.06", table_cell_style)],
    [Paragraph("총 로깅 건수", table_cell_style_bold), Paragraph("2,771건", table_cell_style)],
]
basic_table = Table(basic_info_data, colWidths=[2.5*cm, CONTENT_WIDTH - 2.5*cm])
basic_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), DARK_BLUE),
    ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
    ('BACKGROUND', (0, 1), (0, -1), VERY_LIGHT_GRAY),
    ('GRID', (0, 0), (-1, -1), 0.5, LIGHT_GRAY),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('TOPPADDING', (0, 0), (-1, -1), 4*mm),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 4*mm),
    ('LEFTPADDING', (0, 0), (-1, -1), 6*mm),
    ('RIGHTPADDING', (0, 0), (-1, -1), 6*mm),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, VERY_LIGHT_GRAY]),
]))
story.append(basic_table)
story.append(Spacer(1, 5*mm))

# ============ SECTION 2: SERVICE USAGE ============
story.append(Paragraph("2. 서비스별 사용 현황", section_title_style))
story.append(HRFlowable(width="100%", thickness=1, color=MEDIUM_BLUE))

service_data = [
    [Paragraph("서비스", table_header_style), Paragraph("서비스명", table_header_style), Paragraph("사용 건수", table_header_style), Paragraph("주요 활동", table_header_style)],
    [Paragraph("EMMR", table_cell_style_bold), Paragraph("그룹웨어", table_cell_style), Paragraph("약 1,500건", table_cell_style), Paragraph("업무 메일, 이슈 처리", table_cell_style)],
    [Paragraph("IGBS/IGBR", table_cell_style_bold), Paragraph("Gemini", table_cell_style), Paragraph("약 800건", table_cell_style), Paragraph("기술 연구, AI 학습", table_cell_style)],
    [Paragraph("QSLC", table_cell_style_bold), Paragraph("Slack", table_cell_style), Paragraph("약 200건", table_cell_style), Paragraph("실시간 협업", table_cell_style)],
    [Paragraph("IADS/IAMS", table_cell_style_bold), Paragraph("Adobe/Google", table_cell_style), Paragraph("약 50건", table_cell_style), Paragraph("파일 업로드/다운로드", table_cell_style)],
    [Paragraph("FGIR", table_cell_style_bold), Paragraph("GitHub", table_cell_style), Paragraph("약 10건", table_cell_style), Paragraph("소스 코드 다운로드", table_cell_style)],
]
service_table = Table(service_data, colWidths=[2*cm, 2.5*cm, 2*cm, CONTENT_WIDTH - 6.5*cm])
service_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), DARK_BLUE),
    ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
    ('GRID', (0, 0), (-1, -1), 0.5, LIGHT_GRAY),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('TOPPADDING', (0, 0), (-1, -1), 4*mm),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 4*mm),
    ('LEFTPADDING', (0, 0), (-1, -1), 6*mm),
    ('RIGHTPADDING', (0, 0), (-1, -1), 6*mm),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, VERY_LIGHT_GRAY]),
]))
story.append(service_table)
story.append(Spacer(1, 5*mm))

# ============ SECTION 3: MAIN ACTIVITY ANALYSIS ============
story.append(Paragraph("3. 주요 활동 분석", section_title_style))
story.append(HRFlowable(width="100%", thickness=1, color=MEDIUM_BLUE))

# 3.1 Generative AI
story.append(Paragraph("3.1 생성형 AI 서비스 사용 (Google Gemini)", subsection_title_style))
story.append(Paragraph("주요 IP: 142.251.x.x (Google)", bullet_style))
story.append(Paragraph("AI/ML 기술 연구: HDBSCAN, GLOSH, DBCV, Random Forest 군집화, DeBERTa, LoRA 튜닝", bullet_style))
story.append(Paragraph("인프라 구축: Docker, NVIDIA Container Toolkit, vLLM, Hermes MCP 서버", bullet_style))
story.append(Paragraph("보안 분석: Zeek 로그 분석, DLP 탐지, 생성형 AI 트래픽 식별", bullet_style))
story.append(Paragraph("실무 질문: Slack, MongoDB, ReAct 에이전트 설계, MCP 도구 설계", bullet_style))
story.append(Spacer(1, 3*mm))

# 3.2 Email
story.append(Paragraph("3.2 업무 메일 (EMMR 서비스)", subsection_title_style))
story.append(Paragraph("주요 IP: 35.190.26.143 (xcurenet.daouoffice.com)", bullet_style))

email_items = [
    "ISO27001 인증 관련: 선행개발팀 인프라 점검 스크립트 결과 송부 (2026.06.08)",
    "X-GEN AI 교육: 생성형 AI 보안 솔루션 교육 안내 (2026.05.08)",
    "GS리테일 제안서: 참여인력 이력사항 작성 관련 (2026.05.14)",
    "EMASS 이슈 처리: 다수 이슈 수신 및 처리",
    "계정 생성: 업무서버 계정 생성 관련 (2025.07.07)",
    "명명규칙: 제품 및 모듈 명명규칙 문서 전달 (2026.01.05)",
]
for item in email_items:
    story.append(Paragraph(f"• {item}", bullet_style))
story.append(Spacer(1, 3*mm))

# 3.3 Slack
story.append(Paragraph("3.3 Slack 활동 (QSLC 서비스)", subsection_title_style))
story.append(Paragraph("주요 IP: 35.73.126.78, 35.74.58.174", bullet_style))

slack_items = [
    ("2026.06.01", '"잘하자 몽고db가 왜 나오니", "오늘꺼 다시해"'),
    ("2026.06.01", '"mcp 달았어", "오늘자 김민기 이력 찾아와"'),
    ("2026.05.08", "Docker 컨테이너, NVIDIA GPU 관련 기술 논의"),
    ("2026.04.24", "Hermes MCP 설정 관련 논의"),
]
for date, content in slack_items:
    story.append(Paragraph(f"• {date}: {content}", bullet_style))
story.append(Spacer(1, 3*mm))

# 3.4 EMASS Issues
story.append(Paragraph("3.4 EMASS 이슈 처리", subsection_title_style))

emass_items = [
    ("5433", "[삼성생명서비스] EDC 처리후 /msg/attach/ 경로내 파일 미확인"),
    ("5436", "[삼성전자DS] reindex 토픽 특정 파티션 데이터 미처리"),
    ("5225", "[삼성전기] 수집장비 인입 트래픽의 구글 드라이브 복호화 여부"),
    ("5444", "[SK브로드밴드] 디코더 nolog_any_svctype_ex 설정시 websocket 필터링"),
    ("5441", "[제일기획] Adobe AI 패턴 수정 요청"),
    ("5460", "[X-GEN AI] 개인정보 구분자 차단 미적용"),
    ("5457", "[X-GEN AI] 금칙어 탐지 문제"),
    ("5455", "[X-GEN AI] PII 검출되지 않은 개인정보 탐지/차단"),
    ("5459", "[X-GEN AI] 개인정보 포함된 이미지 PDF 차단 미적용"),
    ("5456", "[X-GEN AI] 인사연동 안한 IP 차단 간헐적 문제"),
]

emass_data = [
    [Paragraph("이슈번호", table_header_style), Paragraph("고객사/내용", table_header_style)],
]
for issue_id, content in emass_items:
    emass_data.append([
        Paragraph(issue_id, table_cell_style_bold),
        Paragraph(content, table_cell_style),
    ])

emass_table = Table(emass_data, colWidths=[2*cm, CONTENT_WIDTH - 2*cm])
emass_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), DARK_BLUE),
    ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
    ('GRID', (0, 0), (-1, -1), 0.5, LIGHT_GRAY),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('TOPPADDING', (0, 0), (-1, -1), 3*mm),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 3*mm),
    ('LEFTPADDING', (0, 0), (-1, -1), 6*mm),
    ('RIGHTPADDING', (0, 0), (-1, -1), 6*mm),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, VERY_LIGHT_GRAY]),
]))
story.append(emass_table)
story.append(PageBreak())

# ============ SECTION 4: SECURITY RISK ANALYSIS ============
story.append(Paragraph("4. 보안 위험도 분석", section_title_style))
story.append(HRFlowable(width="100%", thickness=1, color=MEDIUM_BLUE))

# 4.1 Generative AI usage pattern
story.append(Paragraph("4.1 생성형 AI 서비스 사용 패턴", subsection_title_style))
ai_patterns = [
    "Google Gemini를 업무 목적으로 매우 활발히 사용",
    "Slack에서도 AI 관련 질문 (MCP, MongoDB, ReAct 에이전트)",
    'Slack에서 "오늘자 김민기 이력 찾아와" → Slack에서 AI 도구 사용 시도',
]
for item in ai_patterns:
    story.append(Paragraph(f"• {item}", bullet_style))
story.append(Spacer(1, 3*mm))

# 4.2 Sensitive info exposure
story.append(Paragraph("4.2 민감 정보 노출 가능성", subsection_title_style))
sensitive_items = [
    "Slack 대화에서 MongoDB 쿼리 관련 논의",
    "Docker-compose 설정 파일 공유 (vLLM, Hermes, MongoDB MCP 설정)",
    "내부 IP 대역 (172.x.x.x, 218.234.36.x) 노출",
]
for item in sensitive_items:
    story.append(Paragraph(f"• {item}", bullet_style))
story.append(Spacer(1, 3*mm))

# 4.3 External services
story.append(Paragraph("4.3 외부 서비스 사용", subsection_title_style))
external_data = [
    [Paragraph("서비스", table_header_style), Paragraph("IP 주소", table_header_style), Paragraph("용도", table_header_style)],
    [Paragraph("Google Gemini", table_cell_style_bold), Paragraph("142.251.x.x", table_cell_style), Paragraph("생성형 AI 서비스", table_cell_style)],
    [Paragraph("Slack", table_cell_style_bold), Paragraph("35.73.126.78, 35.74.58.174", table_cell_style), Paragraph("협업 도구", table_cell_style)],
    [Paragraph("GitHub", table_cell_style_bold), Paragraph("185.199.110.133", table_cell_style), Paragraph("파일 다운로드", table_cell_style)],
    [Paragraph("Google AI Mode", table_cell_style_bold), Paragraph("142.250.199.234", table_cell_style), Paragraph("파일 업로드", table_cell_style)],
]
external_table = Table(external_data, colWidths=[2.5*cm, 3*cm, CONTENT_WIDTH - 5.5*cm])
external_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), DARK_BLUE),
    ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
    ('GRID', (0, 0), (-1, -1), 0.5, LIGHT_GRAY),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('TOPPADDING', (0, 0), (-1, -1), 4*mm),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 4*mm),
    ('LEFTPADDING', (0, 0), (-1, -1), 6*mm),
    ('RIGHTPADDING', (0, 0), (-1, -1), 6*mm),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, VERY_LIGHT_GRAY]),
]))
story.append(external_table)
story.append(Spacer(1, 3*mm))

# 4.4 Anomalies
story.append(Paragraph("4.4 이상 징후 (4건)", subsection_title_style))

anomaly_data = [
    [Paragraph("일시", table_header_style), Paragraph("내용", table_header_style)],
]
anomalies = [
    ("2026.06.01 11:37", "Slack에서 \"티베트 독립(Free Tibet) 문제는...\" 관련 Gemini 질문"),
    ("2026.06.01 11:37", "\"티베트가 누구꺼?\"라는 질문"),
    ("2026.06.01 11:37", "\"티베트 프리 인정?\"라는 질문"),
    ("2026.06.01 13:28", "\"과음하고 다음날 심박이 높아지나\" (건강 관련)"),
    ("2026.06.01 10:05", "\"수원 권선동 지방 선거 치뤄야 하는데 누구 뽑을지 공약 정리해줄래\""),
]
for date, content in anomalies:
    anomaly_data.append([
        Paragraph(date, table_cell_style_bold),
        Paragraph(content, table_cell_style),
    ])

anomaly_table = Table(anomaly_data, colWidths=[2.5*cm, CONTENT_WIDTH - 2.5*cm])
anomaly_table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), RED_ACCENT),
    ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
    ('GRID', (0, 0), (-1, -1), 0.5, LIGHT_GRAY),
    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ('TOPPADDING', (0, 0), (-1, -1), 4*mm),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 4*mm),
    ('LEFTPADDING', (0, 0), (-1, -1), 6*mm),
    ('RIGHTPADDING', (0, 0), (-1, -1), 6*mm),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, VERY_LIGHT_GRAY]),
]))
story.append(anomaly_table)
story.append(PageBreak())

# ============ SECTION 5: CONCLUSIONS ============
story.append(Paragraph("5. 결론 및 권고사항", section_title_style))
story.append(HRFlowable(width="100%", thickness=1, color=MEDIUM_BLUE))

story.append(Paragraph("결론", subsection_title_style))
conclusions = [
    "김민기 대리는 AI/ML 연구 및 보안 솔루션 개발에 집중하고 있음",
    "생성형 AI 활용이 활발하나, 민감 정보 노출 가능성에 주의 필요",
]
for item in conclusions:
    story.append(Paragraph(f"• {item}", bullet_style))
story.append(Spacer(1, 3*mm))

story.append(Paragraph("권고사항", subsection_title_style))
recommendations = [
    "Slack 내 기술 논의 시 내부 정보 유출 방지 조치 권고",
    "이상 징후 4건에 대한 추가 모니터링 권고",
]
for item in recommendations:
    story.append(Paragraph(f"• {item}", bullet_style))
story.append(Spacer(1, 5*mm))

# Classification footer
story.append(Spacer(1, 1*cm))
class_box_data = [[Paragraph("⚠️ 내부 문서 - 기밀", ParagraphStyle('ClassBox', parent=styles['Normal'], fontSize=10, textColor=RED_ACCENT, fontName='Helvetica-Bold', alignment=TA_CENTER))]]
class_box = Table(class_box_data, colWidths=[CONTENT_WIDTH])
class_box.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, -1), HexColor("#fff5f5")),
    ('BOX', (0, 0), (-1, -1), 1, RED_ACCENT),
    ('TOPPADDING', (0, 0), (-1, -1), 5*mm),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 5*mm),
    ('LEFTPADDING', (0, 0), (-1, -1), 8*mm),
    ('RIGHTPADDING', (0, 0), (-1, -1), 8*mm),
]))
story.append(class_box)

# Build PDF
doc.build(story, onFirstPage=cover_page, onLaterPages=header_footer)
print(f"PDF generated: {OUTPUT_PATH}")
