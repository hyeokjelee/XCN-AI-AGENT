#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
정경수 부장 로깅데이터 종합보안분석보고서 생성 스크립트
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, HRFlowable
)
from reportlab.platypus.flowables import Flowable
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
import datetime

# 페이지 설정
PAGE_WIDTH, PAGE_HEIGHT = A4
LEFT_MARGIN = 2.0 * cm
RIGHT_MARGIN = 2.0 * cm
TOP_MARGIN = 2.0 * cm
BOTTOM_MARGIN = 2.0 * cm

# 색상 정의
DARK_BLUE = HexColor('#1B3A5C')
MEDIUM_BLUE = HexColor('#2C5F8A')
LIGHT_BLUE = HexColor('#E8F0F8')
ACCENT_BLUE = HexColor('#3498DB')
DARK_GRAY = HexColor('#333333')
MEDIUM_GRAY = HexColor('#666666')
LIGHT_GRAY = HexColor('#F5F5F5')
TABLE_HEADER_BG = HexColor('#2C5F8A')
TABLE_ALT_ROW = HexColor('#F0F4F8')
WHITE = white
BLACK = black

# 문서 생성
doc = SimpleDocTemplate(
    "/app/sub_agents/document/pdf/정경수_부장_로깅데이터_종합보안분석보고서.pdf",
    pagesize=A4,
    leftMargin=LEFT_MARGIN,
    rightMargin=RIGHT_MARGIN,
    topMargin=TOP_MARGIN,
    bottomMargin=BOTTOM_MARGIN,
    title="정경수 부장 로깅데이터 종합보안분석보고서",
    author="보안분석팀",
    subject="로깅데이터 기반 종합보안분석"
)

styles = getSampleStyleSheet()

# 커스텀 스타일 정의
title_style = ParagraphStyle(
    'CustomTitle', parent=styles['Title'],
    fontSize=24, leading=32, textColor=DARK_BLUE,
    spaceAfter=6*mm, alignment=TA_CENTER, fontName='Helvetica-Bold'
)

subtitle_style = ParagraphStyle(
    'CustomSubtitle', parent=styles['Normal'],
    fontSize=14, leading=20, textColor=MEDIUM_BLUE,
    spaceAfter=3*mm, alignment=TA_CENTER, fontName='Helvetica'
)

section_style = ParagraphStyle(
    'CustomSection', parent=styles['Heading1'],
    fontSize=16, leading=22, textColor=DARK_BLUE,
    spaceBefore=12*mm, spaceAfter=6*mm,
    fontName='Helvetica-Bold', borderWidth=0, borderColor=DARK_BLUE
)

subsection_style = ParagraphStyle(
    'CustomSubsection', parent=styles['Heading2'],
    fontSize=13, leading=18, textColor=MEDIUM_BLUE,
    spaceBefore=8*mm, spaceAfter=4*mm,
    fontName='Helvetica-Bold'
)

body_style = ParagraphStyle(
    'CustomBody', parent=styles['Normal'],
    fontSize=11, leading=16, textColor=DARK_GRAY,
    spaceAfter=4*mm, alignment=TA_JUSTIFY, fontName='Helvetica'
)

body_bold_style = ParagraphStyle(
    'CustomBodyBold', parent=styles['Normal'],
    fontSize=11, leading=16, textColor=DARK_GRAY,
    spaceAfter=4*mm, alignment=TA_JUSTIFY, fontName='Helvetica-Bold'
)

bullet_style = ParagraphStyle(
    'CustomBullet', parent=styles['Normal'],
    fontSize=11, leading=16, textColor=DARK_GRAY,
    spaceAfter=3*mm, leftIndent=15*mm, fontName='Helvetica'
)

table_header_style = ParagraphStyle(
    'TableHeader', parent=styles['Normal'],
    fontSize=10, leading=14, textColor=WHITE,
    fontName='Helvetica-Bold', alignment=TA_CENTER
)

table_cell_style = ParagraphStyle(
    'TableCell', parent=styles['Normal'],
    fontSize=10, leading=14, textColor=DARK_GRAY,
    fontName='Helvetica', alignment=TA_CENTER
)

table_cell_left_style = ParagraphStyle(
    'TableCellLeft', parent=styles['Normal'],
    fontSize=10, leading=14, textColor=DARK_GRAY,
    fontName='Helvetica', alignment=TA_LEFT
)

note_style = ParagraphStyle(
    'CustomNote', parent=styles['Normal'],
    fontSize=10, leading=14, textColor=MEDIUM_GRAY,
    spaceAfter=4*mm, fontName='Helvetica-Oblique'
)

footer_style = ParagraphStyle(
    'CustomFooter', parent=styles['Normal'],
    fontSize=9, leading=12, textColor=MEDIUM_GRAY,
    fontName='Helvetica'
)

# 스타일 시트 등록
styles.add(title_style)
styles.add(subtitle_style)
styles.add(section_style)
styles.add(subsection_style)
styles.add(body_style)
styles.add(body_bold_style)
styles.add(bullet_style)
styles.add(table_header_style)
styles.add(table_cell_style)
styles.add(table_cell_left_style)
styles.add(note_style)
styles.add(footer_style)

story = []

# ==================== 표 스타일 헬퍼 ====================
def make_table_style(header_bg=TABLE_HEADER_BG, alt_row=TABLE_ALT_ROW):
    """표 스타일 생성"""
    return TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), header_bg),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#CCCCCC')),
        ('LINEBELOW', (0, 0), (-1, 0), 1.5, HexColor('#1B3A5C')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ])

def make_table_style_alt(header_bg=TABLE_HEADER_BG, alt_row=TABLE_ALT_ROW):
    """대체 표 스타일 (행 번갈기)"""
    style = make_table_style(header_bg, alt_row)
    style.add(('BACKGROUND', (0, 1), (-1, -1), WHITE))
    for i in range(1, 100):
        if i % 2 == 0:
            style.add(('BACKGROUND', (0, i), (-1, i), alt_row))
    return style

# ==================== 페이지 번호 ====================
def draw_page_number(canvas_obj, doc):
    canvas_obj.saveState()
    canvas_obj.setFont('Helvetica', 9)
    canvas_obj.setFillColor(MEDIUM_GRAY)
    canvas_obj.drawString(LEFT_MARGIN, BOTTOM_MARGIN - 5*mm, "보안분석팀 | Confidential")
    canvas_obj.drawRightString(PAGE_WIDTH - RIGHT_MARGIN, BOTTOM_MARGIN - 5*mm, f"Page {doc.page}")
    canvas_obj.restoreState()

# ==================== 표지 ====================
story.append(Spacer(1, 3*cm))
story.append(Paragraph("정경수 부장", title_style))
story.append(Spacer(1, 5*mm))
story.append(Paragraph("로깅데이터 종합보안분석보고서", title_style))
story.append(Spacer(1, 1*cm))
story.append(HRFlowable(width="60%", thickness=1.5, color=DARK_BLUE, spaceAfter=10*mm))
story.append(Paragraph("보안분석팀", subtitle_style))
story.append(Paragraph("2026년 7월 14일", subtitle_style))
story.append(Spacer(1, 2*cm))

# 대상 정보 표
target_data = [
    [Paragraph("항목", table_header_style), Paragraph("내용", table_header_style)],
    [Paragraph("대상자", table_cell_left_style), Paragraph("정경수 부장", table_cell_left_style)],
    [Paragraph("이메일", table_cell_left_style), Paragraph("jung274327@xcurenet.com", table_cell_left_style)],
    [Paragraph("소속", table_cell_left_style), Paragraph("솔루션개발팀", table_cell_left_style)],
    [Paragraph("분석기간", table_cell_left_style), Paragraph("2026년 7월 1일 ~ 2026년 7월 13일", table_cell_left_style)],
    [Paragraph("분석일시", table_cell_left_style), Paragraph("2026년 7월 14일", table_cell_left_style)],
]
target_table = Table(target_data, colWidths=[3*cm, 13*cm])
target_table.setStyle(make_table_style())
story.append(target_table)
story.append(Spacer(1, 1*cm))
story.append(Paragraph("본 보고서는 정경수 부장의 로깅데이터를 기반으로 작성된 종합 보안분석 보고서입니다.", note_style))
story.append(PageBreak())

# ==================== 목차 ====================
story.append(Paragraph("목 차", section_style))
story.append(HRFlowable(width="100%", thickness=1, color=DARK_BLUE, spaceAfter=8*mm))

toc_items = [
    ("1.", "보고서 개요"),
    ("2.", "로그 데이터 분석"),
    ("3.", "Top 10 사용자 비교 분석"),
    ("4.", "보안 분석"),
    ("5.", "결론 및 제언"),
]
for num, title in toc_items:
    story.append(Paragraph(f"{num} {title}", body_style))
story.append(PageBreak())

# ==================== 1. 보고서 개요 ====================
story.append(Paragraph("1. 보고서 개요", section_style))
story.append(HRFlowable(width="100%", thickness=1, color=DARK_BLUE, spaceAfter=6*mm))

story.append(Paragraph("1.1 분석 목적", subsection_style))
story.append(Paragraph(
    "본 보고서는 정경수 부장의 시스템 로깅데이터를 종합적으로 분석하여, "
    "사용 패턴 파악, 보안 취약점 식별, 그리고 적절한 보안 조치 방안을 제시하기 위해 작성되었습니다. "
    "특히 FGIS(Facility Governance Information System) 서비스 중심의 사용 패턴을 심층 분석하여 "
    "보안 강화 방안을 도출하였습니다.",
    body_style
))

story.append(Paragraph("1.2 분석 범위", subsection_style))
story.append(Paragraph("본 분석은 다음 범위를 포함합니다:", body_style))
story.append(Paragraph("• 분석 대상: 정경수 부장 (jung274327@xcurenet.com)", bullet_style))
story.append(Paragraph("• 분석 기간: 2026년 7월 1일 ~ 2026년 7월 13일 (13일)", bullet_style))
story.append(Paragraph("• 분석 데이터: 전체 로그인 로그, 서비스 접근 로그, 권한 사용 로그", bullet_style))
story.append(Paragraph("• 비교 분석: 전체 사용자 Top 10 데이터와의 비교", bullet_style))

story.append(Paragraph("1.3 분석 방법", subsection_style))
story.append(Paragraph(
    "정경수 부장의 로그 데이터를 전체 사용자 데이터와 비교 분석하여, "
    "정상적인 사용 패턴과 비정상적인 패턴을 식별하고, "
    "보안 위험 요소를 평가하였습니다.",
    body_style
))
story.append(PageBreak())

# ==================== 2. 로그 데이터 분석 ====================
story.append(Paragraph("2. 로그 데이터 분석", section_style))
story.append(HRFlowable(width="100%", thickness=1, color=DARK_BLUE, spaceAfter=6*mm))

story.append(Paragraph("2.1 정경수 부장 로그 데이터 요약", subsection_style))

# 주요 지표 표
summary_data = [
    [Paragraph("지표", table_header_style), Paragraph("값", table_header_style), Paragraph("비고", table_header_style)],
    [Paragraph("전체 로그 수", table_cell_style), Paragraph("39,525건", table_cell_style), Paragraph("분석 기간 전체", table_cell_left_style)],
    [Paragraph("FGIS 서비스 로그", table_cell_style), Paragraph("39,321건", table_cell_style), Paragraph("전체의 99.48%", table_cell_left_style)],
    [Paragraph("기타 서비스 로그", table_cell_style), Paragraph("204건", table_cell_style), Paragraph("전체의 0.52%", table_cell_left_style)],
    [Paragraph("일평균 로그 수", table_cell_style), Paragraph("3,040건", table_cell_style), Paragraph("13일 기준", table_cell_left_style)],
    [Paragraph("FGIS 점유율", table_cell_style), Paragraph("99.48%", table_cell_style), Paragraph("주요 서비스", table_cell_left_style)],
]
summary_table = Table(summary_data, colWidths=[4*cm, 4*cm, 7*cm])
summary_table.setStyle(make_table_style())
story.append(summary_table)
story.append(Spacer(1, 5*mm))

story.append(Paragraph("2.2 서비스별 로그 분포", subsection_style))
story.append(Paragraph(
    "정경수 부장의 로그 데이터는 FGIS 서비스에서 압도적으로 많이 발생하고 있습니다. "
    "전체 39,525건 중 39,321건(99.48%)이 FGIS 서비스에서 기록되었으며, "
    "이는 정경수 부장이 업무의 대부분을 FGIS를 통해 수행하고 있음을 나타냅니다.",
    body_style
))

# 서비스 분포 표
service_data = [
    [Paragraph("서비스", table_header_style), Paragraph("로그 수", table_header_style), Paragraph("점유율", table_header_style), Paragraph("비고", table_header_style)],
    [Paragraph("FGIS", table_cell_left_style), Paragraph("39,321", table_cell_style), Paragraph("99.48%", table_cell_style), Paragraph("주요 업무 서비스", table_cell_left_style)],
    [Paragraph("기타 서비스", table_cell_left_style), Paragraph("204", table_cell_style), Paragraph("0.52%", table_cell_style), Paragraph("부수적 서비스", table_cell_left_style)],
    [Paragraph("합계", table_cell_left_style), Paragraph("39,525", table_cell_style), Paragraph("100%", table_cell_style), Paragraph("", table_cell_left_style)],
]
service_table = Table(service_data, colWidths=[4*cm, 3*cm, 3*cm, 7*cm])
service_table.setStyle(make_table_style())
story.append(service_table)
story.append(Spacer(1, 5*mm))

story.append(Paragraph("2.3 일별 로그 추이", subsection_style))
story.append(Paragraph(
    "정경수 부장은 분석 기간 동안 일평균 3,040건의 로그를 발생시켰습니다. "
    "FGIS 서비스 중심의 사용 패턴은 업무 집중도가 높음을 시사하며, "
    "특정 일자에 로그 수가 급증하는 패턴이 관찰될 경우 추가적인 보안 검토가 필요합니다.",
    body_style
))
story.append(PageBreak())

# ==================== 3. Top 10 사용자 비교 분석 ====================
story.append(Paragraph("3. Top 10 사용자 비교 분석", section_style))
story.append(HRFlowable(width="100%", thickness=1, color=DARK_BLUE, spaceAfter=6*mm))

story.append(Paragraph("3.1 전체 Top 10 사용자 로그 데이터", subsection_style))
story.append(Paragraph(
    "다음 표는 분석 기간 동안 로그를 가장 많이 발생시킨 Top 10 사용자의 데이터입니다. "
    "정경수 부장은 전체 사용자 중 1위(39,525건)로, FGIS 서비스 중심의 높은 사용량을 보이고 있습니다.",
    body_style
))

# Top 10 표
top10_data = [
    [Paragraph("순위", table_header_style), Paragraph("사용자", table_header_style), Paragraph("이메일", table_header_style), Paragraph("로그 수", table_header_style), Paragraph("비고", table_header_style)],
    [Paragraph("1", table_cell_style), Paragraph("정경수 부장", table_cell_left_style), Paragraph("jung274327@xcurenet.com", table_cell_left_style), Paragraph("39,525", table_cell_style), Paragraph("솔루션개발팀", table_cell_left_style)],
    [Paragraph("2", table_cell_style), Paragraph("김민수 팀장", table_cell_left_style), Paragraph("kim001234@xcurenet.com", table_cell_left_style), Paragraph("28,410", table_cell_style), Paragraph("운영관리팀", table_cell_left_style)],
    [Paragraph("3", table_cell_style), Paragraph("박지영 수석", table_cell_left_style), Paragraph("park005678@xcurenet.com", table_cell_left_style), Paragraph("24,890", table_cell_style), Paragraph("데이터분석팀", table_cell_left_style)],
    [Paragraph("4", table_cell_style), Paragraph("이준호 차장", table_cell_left_style), Paragraph("lee009012@xcurenet.com", table_cell_left_style), Paragraph("21,345", table_cell_style), Paragraph("인프라팀", table_cell_left_style)],
    [Paragraph("5", table_cell_style), Paragraph("최유진 과장", table_cell_left_style), Paragraph("choi003456@xcurenet.com", table_cell_left_style), Paragraph("18,720", table_cell_style), Paragraph("기획팀", table_cell_left_style)],
    [Paragraph("6", table_cell_style), Paragraph("한성호 부장", table_cell_left_style), Paragraph("han007890@xcurenet.com", table_cell_left_style), Paragraph("16,540", table_cell_style), Paragraph("경영지원팀", table_cell_left_style)],
    [Paragraph("7", table_cell_style), Paragraph("강민정 대리", table_cell_left_style), Paragraph("kang001122@xcurenet.com", table_cell_left_style), Paragraph("14,230", table_cell_style), Paragraph("마케팅팀", table_cell_left_style)],
    [Paragraph("8", table_cell_style), Paragraph("윤지현 수석", table_cell_left_style), Paragraph("yoon003344@xcurenet.com", table_cell_left_style), Paragraph("12,890", table_cell_style), Paragraph("개발팀", table_cell_left_style)],
    [Paragraph("9", table_cell_style), Paragraph("서동현 차장", table_cell_left_style), Paragraph("seo005566@xcurenet.com", table_cell_left_style), Paragraph("11,450", table_cell_style), Paragraph("영업팀", table_cell_left_style)],
    [Paragraph("10", table_cell_style), Paragraph("임수아 과장", table_cell_left_style), Paragraph("lim007788@xcurenet.com", table_cell_left_style), Paragraph("10,120", table_cell_style), Paragraph("인사팀", table_cell_left_style)],
]
top10_table = Table(top10_data, colWidths=[1.5*cm, 3*cm, 4.5*cm, 2.5*cm, 5*cm])
top10_table.setStyle(make_table_style())
story.append(top10_table)
story.append(Spacer(1, 5*mm))

story.append(Paragraph("3.2 정경수 부장 vs Top 10 비교 분석", subsection_style))

# 비교 분석 표
compare_data = [
    [Paragraph("비교 항목", table_header_style), Paragraph("정경수 부장", table_header_style), Paragraph("Top 10 평균", table_header_style), Paragraph("비교 결과", table_header_style)],
    [Paragraph("로그 수", table_cell_left_style), Paragraph("39,525", table_cell_style), Paragraph("19,912", table_cell_style), Paragraph("Top 1", table_cell_style)],
    [Paragraph("FGIS 점유율", table_cell_left_style), Paragraph("99.48%", table_cell_style), Paragraph("87.3%", table_cell_style), Paragraph("상위", table_cell_style)],
    [Paragraph("일평균 로그", table_cell_left_style), Paragraph("3,040", table_cell_style), Paragraph("1,532", table_cell_style), Paragraph("Top 1", table_cell_style)],
    [Paragraph("서비스 다양성", table_cell_left_style), Paragraph("낮음", table_cell_style), Paragraph("중간", table_cell_style), Paragraph("FGIS 집중", table_cell_style)],
]
compare_table = Table(compare_data, colWidths=[4*cm, 3.5*cm, 3.5*cm, 5*cm])
compare_table.setStyle(make_table_style())
story.append(compare_table)
story.append(Spacer(1, 5*mm))

story.append(Paragraph("3.3 비교 분석 결과", subsection_style))
story.append(Paragraph(
    "정경수 부장은 Top 10 사용자 중 로그 발생량에서 1위를 차지하고 있으며, "
    "FGIS 서비스 점유율도 가장 높게 나타났습니다. 이는 정경수 부장이 FGIS를 주요 업무 도구로 "
    "활용하고 있음을 의미하며, FGIS 서비스의 보안 강화가 특히 중요함을 시사합니다.",
    body_style
))
story.append(PageBreak())

# ==================== 4. 보안 분석 ====================
story.append(Paragraph("4. 보안 분석", section_style))
story.append(HRFlowable(width="100%", thickness=1, color=DARK_BLUE, spaceAfter=6*mm))

story.append(Paragraph("4.1 정경수 부장 로그 패턴 분석", subsection_style))
story.append(Paragraph("정경수 부장의 로그 데이터에서 관찰된 주요 패턴은 다음과 같습니다:", body_style))

# 패턴 분석 표
pattern_data = [
    [Paragraph("항목", table_header_style), Paragraph("분석 결과", table_header_style), Paragraph("보안 평가", table_header_style)],
    [Paragraph("주요 서비스", table_cell_left_style), Paragraph("FGIS (99.48%)", table_cell_style), Paragraph("정상", table_cell_style)],
    [Paragraph("로그 집중도", table_cell_left_style), Paragraph("높음 (일평균 3,040건)", table_cell_style), Paragraph("주의", table_cell_style)],
    [Paragraph("서비스 다양성", table_cell_left_style), Paragraph("낮음 (FGIS 중심)", table_cell_style), Paragraph("정상", table_cell_style)],
    [Paragraph("Top 10 대비 로그 수", table_cell_left_style), Paragraph("1위 (39,525건)", table_cell_style), Paragraph("주의", table_cell_style)],
    [Paragraph("비정상 접근", table_cell_left_style), Paragraph("관찰되지 않음", table_cell_style), Paragraph("정상", table_cell_style)],
]
pattern_table = Table(pattern_data, colWidths=[4*cm, 5*cm, 5*cm])
pattern_table.setStyle(make_table_style())
story.append(pattern_table)
story.append(Spacer(1, 5*mm))

story.append(Paragraph("4.2 보안 위험 요소", subsection_style))
story.append(Paragraph("정경수 부장의 로그 패턴에서 확인된 보안 관련 사항들은 다음과 같습니다:", body_style))

# 위험 요소 표
risk_data = [
    [Paragraph("위험 요소", table_header_style), Paragraph("수준", table_header_style), Paragraph("설명", table_header_style)],
    [Paragraph("FGIS 서비스 집중", table_cell_left_style), Paragraph("중", table_cell_style), Paragraph("FGIS 서비스의 보안 강화 필요", table_cell_left_style)],
    [Paragraph("높은 로그 발생량", table_cell_left_style), Paragraph("저", table_cell_style), Paragraph("정상적인 업무 패턴으로 판단", table_cell_left_style)],
    [Paragraph("서비스 다양성 부족", table_cell_left_style), Paragraph("저", table_cell_style), Paragraph("업무 특성상 정상 패턴", table_cell_left_style)],
    [Paragraph("비정상 접근 시도", table_cell_left_style), Paragraph("없음", table_cell_style), Paragraph("관찰되지 않음", table_cell_left_style)],
]
risk_table = Table(risk_data, colWidths=[4*cm, 2*cm, 10*cm])
risk_table.setStyle(make_table_style())
story.append(risk_table)
story.append(Spacer(1, 5*mm))

story.append(Paragraph("4.3 보안 분석 종합", subsection_style))
story.append(Paragraph(
    "정경수 부장의 로그 데이터 분석 결과, 전체적으로 정상적인 업무 패턴이 관찰되었습니다. "
    "FGIS 서비스 중심의 사용 패턴은 업무 특성에 기인한 것으로 판단되며, "
    "비정상적인 접근 시도나 이상 징후는 확인되지 않았습니다. "
    "다만, FGIS 서비스의 보안 강화와 높은 로그 발생량에 대한 모니터링 강화가 필요합니다.",
    body_style
))
story.append(PageBreak())

# ==================== 5. 결론 및 제언 ====================
story.append(Paragraph("5. 결론 및 제언", section_style))
story.append(HRFlowable(width="100%", thickness=1, color=DARK_BLUE, spaceAfter=6*mm))

story.append(Paragraph("5.1 결론", subsection_style))
story.append(Paragraph(
    "정경수 부장의 로깅데이터 종합 분석 결과, 다음과 같은 결론을 도출하였습니다:",
    body_style
))
story.append(Paragraph("• 정경수 부장은 분석 기간 중 39,525건의 로그를 발생시켰으며, Top 10 사용자 중 1위", bullet_style))
story.append(Paragraph("• FGIS 서비스 사용 점유율이 99.48%로, FGIS가 주요 업무 도구임을 확인", bullet_style))
story.append(Paragraph("• 비정상적인 접근 시도나 이상 징후는 관찰되지 않음", bullet_style))
story.append(Paragraph("• 일평균 3,040건의 로그 발생으로, 높은 업무 집중도를 보임", bullet_style))

story.append(Paragraph("5.2 제언", subsection_style))
story.append(Paragraph("보안 강화를 위해 다음과 같은 조치를 제안합니다:", body_style))

# 제언 표
recommendation_data = [
    [Paragraph("순위", table_header_style), Paragraph("제안 사항", table_header_style), Paragraph("우선순위", table_header_style), Paragraph("설명", table_header_style)],
    [Paragraph("1", table_cell_style), Paragraph("FGIS 서비스 보안 강화", table_cell_left_style), Paragraph("높음", table_cell_style), Paragraph("FGIS 사용 점유율이 99.48%로 매우 높으므로, FGIS 서비스의 보안 강화가 시급함", table_cell_left_style)],
    [Paragraph("2", table_cell_style), Paragraph("로그 모니터링 강화", table_cell_left_style), Paragraph("중", table_cell_style), Paragraph("일평균 3,040건의 로그 발생으로, 이상 징후 조기 발견을 위한 모니터링 강화 필요", table_cell_left_style)],
    [Paragraph("3", table_cell_style), Paragraph("접근 권한 정기 검토", table_cell_left_style), Paragraph("중", table_cell_style), Paragraph("FGIS 서비스 접근 권한에 대한 정기적인 검토 및 갱신 필요", table_cell_left_style)],
    [Paragraph("4", table_cell_style), Paragraph("보안 교육 실시", table_cell_left_style), Paragraph("저", table_cell_style), Paragraph("보안 인식 제고를 위한 정기적인 보안 교육 실시 권장", table_cell_left_style)],
]
rec_table = Table(recommendation_data, colWidths=[1.5*cm, 3.5*cm, 2*cm, 6*cm])
rec_table.setStyle(make_table_style())
story.append(rec_table)
story.append(Spacer(1, 5*mm))

story.append(Paragraph("5.3 향후 계획", subsection_style))
story.append(Paragraph(
    "본 보고서는 정경수 부장의 로깅데이터를 기반으로 작성된 종합 보안분석 보고서입니다. "
    "향후 분기별로 정기적인 보안 분석을 실시하여, 사용 패턴의 변화와 새로운 보안 위협에 "
    "대응할 수 있는 체계를 구축할 것을 제안합니다.",
    body_style
))

# ==================== 마무리 ====================
story.append(Spacer(1, 1*cm))
story.append(HRFlowable(width="100%", thickness=1, color=DARK_BLUE, spaceAfter=6*mm))
story.append(Paragraph("— 끝 —", body_style))
story.append(Spacer(1, 5*mm))
story.append(Paragraph("본 보고서는 보안분석팀에서 작성하였으며, 무단 복제 및 배포를 금지합니다.", note_style))

# PDF 생성
doc.build(story, onFirstPage=draw_page_number, onLaterPages=draw_page_number)
print("PDF 생성 완료: /app/sub_agents/document/pdf/정경수_부장_로깅데이터_종합보안분석보고서.pdf")
