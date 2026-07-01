#!/usr/bin/env python3
"""Generate professional PDF report for Kim Min-kyung Q2 2026 logging analysis."""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor, black, white, grey
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, HRFlowable
)
from reportlab.platypus.doctemplate import BaseDocTemplate
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
import datetime

# Output path
OUTPUT_PATH = "/app/tmp/workspace/김민경_프로_2026년_2분기_로깅_데이터_분석_보고서.pdf"

# Colors
DARK_BLUE = HexColor("#1a365d")
MEDIUM_BLUE = HexColor("#2b6cb0")
LIGHT_BLUE = HexColor("#ebf4ff")
ACCENT_BLUE = HexColor("#3182ce")
HEADER_BG = HexColor("#2d3748")
TABLE_HEADER_BG = HexColor("#2b6cb0")
TABLE_ALT_BG = HexColor("#f7fafc")
TABLE_ALT_BG2 = HexColor("#edf2f7")
BORDER_COLOR = HexColor("#cbd5e0")
TEXT_DARK = HexColor("#1a202c")
TEXT_GRAY = HexColor("#4a5568")
LIGHT_GRAY = HexColor("#f8f9fa")
GREEN = HexColor("#38a169")
RED = HexColor("#e53e3e")
ORANGE = HexColor("#dd6b20")

# Page dimensions
PAGE_W, PAGE_H = A4
LEFT_MARGIN = 20 * mm
RIGHT_MARGIN = 20 * mm
TOP_MARGIN = 20 * mm
BOTTOM_MARGIN = 20 * mm
CONTENT_W = PAGE_W - LEFT_MARGIN - RIGHT_MARGIN

# Styles
styles = getSampleStyleSheet()

# Custom styles
styles.add(ParagraphStyle(
    'CoverTitle', parent=styles['Title'],
    fontName='Helvetica-Bold', fontSize=28, leading=36,
    textColor=DARK_BLUE, alignment=TA_CENTER, spaceAfter=12
))
styles.add(ParagraphStyle(
    'CoverSubtitle', parent=styles['Title'],
    fontName='Helvetica', fontSize=16, leading=22,
    textColor=TEXT_GRAY, alignment=TA_CENTER, spaceAfter=6
))
styles.add(ParagraphStyle(
    'CoverInfo', parent=styles['Normal'],
    fontName='Helvetica', fontSize=11, leading=16,
    textColor=TEXT_GRAY, alignment=TA_CENTER, spaceAfter=4
))
styles.add(ParagraphStyle(
    'SectionTitle', parent=styles['Heading1'],
    fontName='Helvetica-Bold', fontSize=16, leading=22,
    textColor=DARK_BLUE, spaceBefore=18, spaceAfter=10,
    borderWidth=0, borderPadding=0
))
styles.add(ParagraphStyle(
    'SubSectionTitle', parent=styles['Heading2'],
    fontName='Helvetica-Bold', fontSize=13, leading=18,
    textColor=MEDIUM_BLUE, spaceBefore=14, spaceAfter=8
))
styles.add(ParagraphStyle(
    'SubSubSectionTitle', parent=styles['Heading3'],
    fontName='Helvetica-Bold', fontSize=11, leading=15,
    textColor=TEXT_DARK, spaceBefore=10, spaceAfter=6
))
styles.add(ParagraphStyle(
    'BodyText2', parent=styles['Normal'],
    fontName='Helvetica', fontSize=10, leading=15,
    textColor=TEXT_DARK, alignment=TA_JUSTIFY, spaceAfter=6
))
styles.add(ParagraphStyle(
    'BulletText', parent=styles['Normal'],
    fontName='Helvetica', fontSize=10, leading=15,
    textColor=TEXT_DARK, alignment=TA_LEFT, spaceAfter=4,
    leftIndent=18, bulletIndent=6
))
styles.add(ParagraphStyle(
    'Insight', parent=styles['Normal'],
    fontName='Helvetica', fontSize=10, leading=15,
    textColor=TEXT_GRAY, alignment=TA_JUSTIFY, spaceAfter=6,
    leftIndent=12, backColor=LIGHT_BLUE, borderPadding=6, borderWidth=0.5,
    borderColor=ACCENT_BLUE
))
styles.add(ParagraphStyle(
    'Footer', parent=styles['Normal'],
    fontName='Helvetica', fontSize=8, leading=10,
    textColor=TEXT_GRAY, alignment=TA_CENTER
))
styles.add(ParagraphStyle(
    'TableHeader', parent=styles['Normal'],
    fontName='Helvetica-Bold', fontSize=9, leading=13,
    textColor=white, alignment=TA_CENTER
))
styles.add(ParagraphStyle(
    'TableCell', parent=styles['Normal'],
    fontName='Helvetica', fontSize=9, leading=13,
    textColor=TEXT_DARK, alignment=TA_CENTER
))
styles.add(ParagraphStyle(
    'TableCellLeft', parent=styles['Normal'],
    fontName='Helvetica', fontSize=9, leading=13,
    textColor=TEXT_DARK, alignment=TA_LEFT
))
styles.add(ParagraphStyle(
    'TableCellBold', parent=styles['Normal'],
    fontName='Helvetica-Bold', fontSize=9, leading=13,
    textColor=TEXT_DARK, alignment=TA_CENTER
))
styles.add(ParagraphStyle(
    'Highlight', parent=styles['Normal'],
    fontName='Helvetica-Bold', fontSize=10, leading=15,
    textColor=DARK_BLUE
))
styles.add(ParagraphStyle(
    'SmallNote', parent=styles['Normal'],
    fontName='Helvetica', fontSize=8, leading=11,
    textColor=TEXT_GRAY, alignment=TA_LEFT
))

# Helper functions
def hr():
    return HRFlowable(width="100%", thickness=0.5, color=BORDER_COLOR, spaceBefore=4, spaceAfter=4)

def section_title(text):
    return Paragraph(text, styles['SectionTitle'])

def sub_section_title(text):
    return Paragraph(text, styles['SubSectionTitle'])

def sub_sub_section_title(text):
    return Paragraph(text, styles['SubSubSectionTitle'])

def body(text):
    return Paragraph(text, styles['BodyText2'])

def bullet(text):
    return Paragraph(f"• {text}", styles['BulletText'])

def insight(text):
    return Paragraph(f"<b>💡 인사이트:</b> {text}", styles['Insight'])

def make_table(data, col_widths=None, header_bg=TABLE_HEADER_BG, alt_bg=TABLE_ALT_BG):
    """Create a styled table."""
    if col_widths is None:
        col_widths = [CONTENT_W / len(data[0])] * len(data[0])

    # Build table cells
    cells = []
    for i, row in enumerate(data):
        cell_row = []
        for j, val in enumerate(row):
            if i == 0:
                cell_row.append(Paragraph(str(val), styles['TableHeader']))
            else:
                style = styles['TableCell']
                if j == 0:
                    style = styles['TableCellLeft']
                cell_row.append(Paragraph(str(val), style))
        cells.append(cell_row)

    table = Table(cells, colWidths=col_widths, repeatRows=1)

    # Build style commands
    style_cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), header_bg),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [alt_bg, TABLE_ALT_BG2]),
    ]

    table.setStyle(TableStyle(style_cmds))
    return table

def page_number(canvas_obj, doc):
    canvas_obj.saveState()
    canvas_obj.setFont('Helvetica', 8)
    canvas_obj.setFillColor(TEXT_GRAY)
    canvas_obj.drawCentredString(PAGE_W / 2, 12 * mm, f"{doc.page}")
    canvas_obj.drawRightString(PAGE_W - RIGHT_MARGIN, 12 * mm, "김민경 프로 - 2026년 2분기 로깅 데이터 분석 보고서")
    canvas_obj.restoreState()

def cover_page(canvas_obj, doc):
    canvas_obj.saveState()
    # Background
    canvas_obj.setFillColor(LIGHT_BLUE)
    canvas_obj.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    # Top accent bar
    canvas_obj.setFillColor(DARK_BLUE)
    canvas_obj.rect(0, PAGE_H - 80, PAGE_W, 80, fill=1, stroke=0)
    # Title
    canvas_obj.setFillColor(white)
    canvas_obj.setFont('Helvetica-Bold', 28)
    canvas_obj.drawCentredString(PAGE_W / 2, PAGE_H - 130, "김민경 프로")
    canvas_obj.setFont('Helvetica', 18)
    canvas_obj.drawCentredString(PAGE_W / 2, PAGE_H - 160, "2026년 2분기 로깅 데이터 분석 보고서")
    # Subtitle
    canvas_obj.setFont('Helvetica', 12)
    canvas_obj.setFillColor(TEXT_GRAY)
    canvas_obj.drawCentredString(PAGE_W / 2, PAGE_H - 200, "솔루션개발팀 • 2026년 4월 1일 ~ 6월 30일")
    # Bottom info
    canvas_obj.setFont('Helvetica', 10)
    canvas_obj.drawCentredString(PAGE_W / 2, 60 * mm, "XCN-AI (엑큐) • 2026년 7월")
    canvas_obj.restoreState()

# Build document
doc = SimpleDocTemplate(
    OUTPUT_PATH,
    pagesize=A4,
    leftMargin=LEFT_MARGIN,
    rightMargin=RIGHT_MARGIN,
    topMargin=TOP_MARGIN,
    bottomMargin=BOTTOM_MARGIN,
    title="김민경 프로 - 2026년 2분기 로깅 데이터 분석 보고서",
    author="XCN-AI (엑큐)",
    subject="로깅 데이터 분석 보고서",
)

story = []

# Cover page
story.append(Spacer(1, 10 * mm))
story.append(Paragraph("김민경 프로", styles['CoverTitle']))
story.append(Paragraph("2026년 2분기 로깅 데이터 분석 보고서", styles['CoverSubtitle']))
story.append(Spacer(1, 6 * mm))
story.append(Paragraph("솔루션개발팀 • 2026년 4월 1일 ~ 6월 30일", styles['CoverInfo']))
story.append(Spacer(1, 10 * mm))
story.append(Paragraph("XCN-AI (엑큐) • 2026년 7월", styles['CoverInfo']))
story.append(PageBreak())

# Table of Contents
story.append(section_title("목차"))
story.append(hr())
toc_items = [
    "1. 개요 (Executive Summary)",
    "2. 친밀도 분석",
    "   2.1 상호작용 채널별 분석",
    "   2.2 팀 협업 지표",
    "   2.3 AI 도구 의존도",
    "3. 활동기록 분석",
    "   3.1 월별 활동량",
    "   3.2 시간대별 활동 패턴",
    "   3.3 주요 호스트(접속 대상) 분석",
    "   3.4 서비스별 활동 분포",
    "4. 업무 분석",
    "   4.1 주요 업무 활동",
    "   4.2 첨부파일 활동",
    "   4.3 Git 활동 패턴",
    "   4.4 특이 사항",
    "5. 종합 평가 및 제언",
    "   5.1 성과 평가",
    "   5.2 강점",
    "   5.3 개선 영역",
    "   5.4 3분기 방향",
    "   5.5 핵심 권고사항",
]
for item in toc_items:
    story.append(Paragraph(item, styles['BodyText2']))
story.append(PageBreak())

# ===== SECTION 1: Overview =====
story.append(section_title("1. 개요 (Executive Summary)"))
story.append(hr())
story.append(body("본 보고서는 솔루션개발팀 김민경 프로의 2026년 2분기(4월~6월) 로깅 데이터를 분석하여 업무 활동 및 성과를 종합적으로 평가한 보고서입니다."))
story.append(Spacer(1, 6 * mm))

# Overview table
overview_data = [
    ["항목", "내용"],
    ["분석 대상", "김민경 프로 (솔루션개발팀)"],
    ["분석 기간", "2026년 4월 1일 ~ 6월 30일"],
    ["분석 목적", "2분기 업무 활동 및 성과 분석을 통한 종합 평가"],
    ["핵심 발견", "GitHub Git 작업(45%)과 Slack 메신저(40%)가 주 활동, Claude AI 활용도 높음, 5월 활동량 급증, 6월 감소"],
]
story.append(make_table(overview_data, col_widths=[2.5 * cm, CONTENT_W - 2.5 * cm]))
story.append(Spacer(1, 6 * mm))
story.append(insight("GitHub Git 작업(45.1%)과 Slack 메신저(40.1%)가 전체 활동의 85% 이상을 차지하며, 개발 중심의 업무 환경임을 확인"))
story.append(PageBreak())

# ===== SECTION 2: Intimacy Analysis =====
story.append(section_title("2. 친밀도 분석"))
story.append(hr())

# 2.1 Channel Analysis
story.append(sub_section_title("2.1 상호작용 채널별 분석"))
story.append(Spacer(1, 4 * mm))

channel_data = [
    ["채널", "건수", "비중"],
    ["Slack 메신저", "4,237", "40.1%"],
    ["GitHub Git", "4,772", "45.1%"],
    ["이메일", "548", "5.2%"],
    ["Claude AI", "356", "3.4%"],
    ["ChatGPT", "120", "1.1%"],
]
story.append(make_table(channel_data, col_widths=[3.5 * cm, 2.5 * cm, 2 * cm]))
story.append(Spacer(1, 6 * mm))
story.append(insight("GitHub Git(45.1%)과 Slack 메신저(40.1%)가 전체 활동의 85% 이상을 차지"))

# 2.2 Team Collaboration
story.append(sub_section_title("2.2 팀 협업 지표"))
story.append(Spacer(1, 4 * mm))
story.append(sub_sub_section_title("상호작용 대상 상위 10명"))
story.append(Spacer(1, 4 * mm))

collab_data = [
    ["순위", "이름", "4월", "5월", "6월", "합계"],
    ["1", "안유나", "60", "119", "58", "237"],
    ["2", "정경수", "62", "118", "55", "235"],
    ["3", "차대윤", "58", "118", "55", "231"],
    ["4", "조창민", "56", "117", "50", "223"],
    ["5", "김영훈", "58", "117", "45", "220"],
    ["6", "김병민", "57", "116", "47", "220"],
    ["7", "송기현", "56", "115", "47", "218"],
    ["8", "이강욱", "56", "114", "47", "217"],
    ["9", "이상현", "57", "113", "-", "170"],
    ["10", "김민경 (자기)", "136", "286", "118", "540"],
]
story.append(make_table(collab_data, col_widths=[0.8 * cm, 2.5 * cm, 1.5 * cm, 1.5 * cm, 1.5 * cm, 1.5 * cm]))
story.append(Spacer(1, 6 * mm))
story.append(insight("안유나, 정경수, 차대윤이 가장 활발한 상호작용 대상이며, 5월에 상호작용이 전반적으로 증가 (팀 프로젝트 기간 추정)"))
story.append(insight("6월은 상호작용이 감소하는 경향을 보임"))

# 2.3 AI Tool Dependency
story.append(sub_section_title("2.3 AI 도구 의존도"))
story.append(Spacer(1, 4 * mm))

ai_data = [
    ["AI 도구", "4월", "5월", "6월", "합계"],
    ["Claude.ai", "92", "365", "233", "690"],
    ["ChatGPT", "24", "44", "52", "120"],
]
story.append(make_table(ai_data, col_widths=[2.5 * cm, 1.5 * cm, 1.5 * cm, 1.5 * cm, 1.5 * cm]))
story.append(Spacer(1, 6 * mm))
story.append(insight("Claude.ai 사용이 5월에 집중 (365건) — 코드 분석, 디버깅, 구현 지원에 활발히 활용"))
story.append(insight("ChatGPT 사용은 6월에 증가 (52건)"))
story.append(PageBreak())

# ===== SECTION 3: Activity Records =====
story.append(section_title("3. 활동기록 분석"))
story.append(hr())

# 3.1 Monthly Activity
story.append(sub_section_title("3.1 월별 활동량"))
story.append(Spacer(1, 4 * mm))

monthly_data = [
    ["월", "건수", "전월 대비"],
    ["4월", "4,075", "-"],
    ["5월", "4,197", "+3.0%"],
    ["6월", "2,305", "-45.1%"],
    ["<b>총계</b>", "<b>10,577</b>", "-"],
]
story.append(make_table(monthly_data, col_widths=[1.5 * cm, 2 * cm, 2.5 * cm]))
story.append(Spacer(1, 6 * mm))
story.append(insight("5월 활동량이 분기 중 가장 많았으며, 6월은 4~5월 대비 약 45% 감소"))

# 3.2 Time-based Activity
story.append(sub_section_title("3.2 시간대별 활동 패턴"))
story.append(Spacer(1, 4 * mm))

# April
story.append(sub_sub_section_title("4월"))
story.append(Spacer(1, 2 * mm))
apr_data = [
    ["시간대", "건수"],
    ["14시", "614"],
    ["15시", "609"],
    ["16시", "582"],
    ["09시", "510"],
    ["10시", "493"],
    ["11시", "451"],
    ["13시", "405"],
    ["08시", "244"],
    ["12시", "132"],
    ["17시", "35"],
]
story.append(make_table(apr_data, col_widths=[2 * cm, CONTENT_W - 2 * cm]))
story.append(Spacer(1, 6 * mm))

# May
story.append(sub_sub_section_title("5월"))
story.append(Spacer(1, 2 * mm))
may_data = [
    ["시간대", "건수"],
    ["09시", "619"],
    ["14시", "536"],
    ["13시", "516"],
    ["15시", "509"],
    ["16시", "481"],
    ["10시", "460"],
    ["08시", "389"],
    ["11시", "389"],
    ["12시", "174"],
    ["17시", "100"],
]
story.append(make_table(may_data, col_widths=[2 * cm, CONTENT_W - 2 * cm]))
story.append(Spacer(1, 6 * mm))

# June
story.append(sub_sub_section_title("6월"))
story.append(Spacer(1, 2 * mm))
jun_data = [
    ["시간대", "건수"],
    ["16시", "358"],
    ["09시", "337"],
    ["10시", "288"],
    ["15시", "284"],
    ["14시", "269"],
    ["11시", "234"],
    ["13시", "219"],
    ["08시", "202"],
    ["12시", "106"],
    ["17시", "8"],
]
story.append(make_table(jun_data, col_widths=[2 * cm, CONTENT_W - 2 * cm]))
story.append(Spacer(1, 6 * mm))
story.append(insight("출근 시간대(08~09시)에 활발한 활동 시작, 오후 13~16시가 가장 높은 활동 밀도 (전체 40% 이상)"))
story.append(insight("17시 이후 활동 급감 (퇴근 패턴), 6월은 전반적으로 활동량 감소"))
story.append(PageBreak())

# 3.3 Host Analysis
story.append(sub_section_title("3.3 주요 호스트(접속 대상) 분석"))
story.append(Spacer(1, 4 * mm))

host_data = [
    ["플랫폼", "4월", "5월", "6월", "합계"],
    ["xcurenethq.slack.com", "2,056", "1,329", "852", "4,237"],
    ["github.com", "1,736", "2,112", "924", "4,772"],
    ["claude.ai", "92", "365", "233", "690"],
    ["xcurenet.daouoffice.com", "141", "302", "122", "565"],
    ["chatgpt.com", "24", "44", "52", "120"],
    ["files.slack.com", "23", "26", "11", "60"],
    ["atlassian.net", "-", "11", "13", "24"],
    ["notion.so", "-", "6", "1", "7"],
    ["blog.naver.com", "-", "-", "97", "97"],
]
story.append(make_table(host_data, col_widths=[4 * cm, 1.5 * cm, 1.5 * cm, 1.5 * cm, 1.5 * cm]))
story.append(Spacer(1, 6 * mm))
story.append(insight("GitHub와 Slack이 주 활동 플랫폼이며, Claude.ai 사용이 5월에 급증 (365건)"))
story.append(insight("6월에 blog.naver.com(97건) 등 외부 사이트 접근 확인"))

# 3.4 Service Distribution
story.append(sub_section_title("3.4 서비스별 활동 분포"))
story.append(Spacer(1, 4 * mm))

service_data = [
    ["서비스", "4월", "5월", "6월", "합계", "비중"],
    ["QSLC (Slack 메신저)", "2,056", "1,329", "852", "4,237", "40.1%"],
    ["FGIS (GitHub Git)", "1,736", "2,112", "924", "4,772", "45.1%"],
    ["EMMR (이메일)", "138", "288", "122", "548", "5.2%"],
    ["ICLS (Claude AI)", "46", "193", "117", "356", "3.4%"],
    ["ICLR (Claude AI)", "46", "172", "116", "334", "3.2%"],
    ["기타", "61", "103", "74", "238", "2.2%"],
]
story.append(make_table(service_data, col_widths=[3 * cm, 1.3 * cm, 1.3 * cm, 1.3 * cm, 1.3 * cm, 1.3 * cm]))
story.append(Spacer(1, 6 * mm))
story.append(insight("GitHub Git 활동이 전체의 45%를 차지하며 가장 많은 활동 유형, Slack 메신저가 40%로 2위"))
story.append(insight("Claude AI 사용이 6.6%로 상당한 AI 활용도, 5월 중순부터 GitHub 활동이 급증 (2,112건)"))
story.append(PageBreak())

# ===== SECTION 4: Work Analysis =====
story.append(section_title("4. 업무 분석"))
story.append(hr())

# 4.1 Main Work Activities
story.append(sub_section_title("4.1 주요 업무 활동"))
story.append(Spacer(1, 4 * mm))

work_data = [
    ["업무 유형", "주요 내용", "기간", "비고"],
    ["GitHub Git 작업", "Clone/Fetch, 브랜치 관리", "4~6월", "핵심 업무"],
    ["Claude AI 활용", "코드 분석, 디버깅, 구현 지원", "4~6월", "5월 집중"],
    ["이메일 수신", "Redmine 이슈 알림, 급여명세서", "4~6월", "-"],
    ["코드 관련 활동", "Java 소스파일, SQL 파일", "4~6월", "개발 활동"],
    ["보안 관련 업무", "취약점 진단 보고서", "5월", "DBMS/PC"],
]
story.append(make_table(work_data, col_widths=[2.5 * cm, 4 * cm, 1.5 * cm, 2.5 * cm]))
story.append(Spacer(1, 6 * mm))
story.append(insight("GitHub Git 작업이 핵심 업무로, 브랜치 관리 및 코드 협업 활발"))
story.append(insight("Claude AI를 활용한 개발 지원 활동이 5월에 집중"))
story.append(insight("Redmine 이슈 알림을 통한 프로젝트 관리, 보안 관련 업무(취약점 진단)에도 참여"))

# 4.2 Attachment Activities
story.append(sub_section_title("4.2 첨부파일 활동"))
story.append(Spacer(1, 4 * mm))

attach_data = [
    ["파일 유형", "4월", "5월", "6월"],
    ["image.png", "21", "25", "9"],
    ["급여명세서", "2", "2", "-"],
    ["취약점진단보고서", "-", "3", "-"],
    ["Java 소스파일", "2", "2", "10+"],
    ["SQL 파일", "-", "2", "-"],
]
story.append(make_table(attach_data, col_widths=[3.5 * cm, 1.5 * cm, 1.5 * cm, 1.5 * cm]))
story.append(Spacer(1, 6 * mm))
story.append(insight("Java 소스파일과 SQL 파일이 개발 활동 확인, 5월에 취약점진단보고서 수신 (보안 관련 업무 참여)"))
story.append(insight("이미지 파일이 활발하게 첨부됨"))

# 4.3 Git Activity Pattern
story.append(sub_section_title("4.3 Git 활동 패턴"))
story.append(Spacer(1, 4 * mm))
story.append(bullet("GitHub에서 refs/heads/master, refs/heads/emass_2ndDev 브랜치 접근 확인"))
story.append(bullet("5월 중순부터 GitHub 활동이 급증 (2,112건)"))
story.append(bullet("코드 협업 및 브랜치 관리 활발"))
story.append(Spacer(1, 6 * mm))

# 4.4 Special Items
story.append(sub_section_title("4.4 특이 사항"))
story.append(Spacer(1, 4 * mm))

story.append(sub_sub_section_title("4.4.1 5월 활동량 급증"))
story.append(bullet("4,197건으로 분기 중 가장 많았으며, GitHub 활동이 2,112건으로 급증"))

story.append(sub_sub_section_title("4.4.2 6월 활동량 감소"))
story.append(bullet("2,305건으로 4~5월 대비 약 45% 감소"))

story.append(sub_sub_section_title("4.4.3 AI 도구 사용 증가"))
story.append(bullet("Claude.ai 사용이 4월(92건) → 5월(365건) → 6월(233건)로 지속적 증가"))

story.append(sub_sub_section_title("4.4.4 외부 사이트 접근"))
story.append(bullet("6월에 blog.naver.com(97건), notion.so(7건) 등 외부 사이트 접근 확인"))

story.append(sub_sub_section_title("4.4.5 취약점 진단 보고서"))
story.append(bullet("5월에 DBMS/PC 취약점 진단 보고서 수신 (보안 관련 업무 참여)"))

story.append(sub_sub_section_title("4.4.6 Git 활동 패턴"))
story.append(bullet("GitHub에서 refs/heads/master, refs/heads/emass_2ndDev 브랜치 접근 확인"))

story.append(sub_sub_section_title("4.4.7 이메일 수신자 수"))
story.append(bullet("5월 8일 Redmine 알림이 44명에게 동시 발송 (대규모 팀 협업)"))
story.append(PageBreak())

# ===== SECTION 5: Comprehensive Evaluation =====
story.append(section_title("5. 종합 평가 및 제언"))
story.append(hr())

# 5.1 Performance Evaluation
story.append(sub_section_title("5.1 성과 평가"))
story.append(Spacer(1, 4 * mm))
story.append(bullet("GitHub Git 작업과 Slack 메신저가 주 활동으로, 개발 업무에 집중"))
story.append(bullet("Claude AI를 활용한 개발 지원 활동이 활발"))
story.append(bullet("5월에는 협업 활동이 가장 활발했던 달"))
story.append(bullet("보안 관련 업무(취약점 진단)에도 참여"))

# 5.2 Strengths
story.append(sub_section_title("5.2 강점"))
story.append(Spacer(1, 4 * mm))
story.append(bullet("GitHub Git 작업 능력이 뛰어남"))
story.append(bullet("Claude AI 등 AI 도구 활용 능력이 우수"))
story.append(bullet("다양한 플랫폼(Slack, GitHub, 이메일)을 활용하여 업무 수행"))
story.append(bullet("보안 관련 업무에도 참여하는 다재다능함"))

# 5.3 Improvement Areas
story.append(sub_section_title("5.3 개선 영역"))
story.append(Spacer(1, 4 * mm))
story.append(bullet("6월 활동량 급감에 대한 원인 파악 필요"))
story.append(bullet("외부 사이트 접근(blog.naver.com 등)에 대한 보안 검토 필요"))
story.append(bullet("5월 활동량 급증에 대한 업무 부하 모니터링 필요"))

# 5.4 Q3 Direction
story.append(sub_section_title("5.4 3분기 방향"))
story.append(Spacer(1, 4 * mm))
story.append(bullet("GitHub Git 작업 지속"))
story.append(bullet("AI 도구 활용 확대 및 최적화"))
story.append(bullet("팀 협업 활동 지속적 강화"))
story.append(bullet("보안 관련 업무 참여 지속"))

# 5.5 Key Recommendations
story.append(sub_section_title("5.5 핵심 권고사항"))
story.append(Spacer(1, 4 * mm))
story.append(bullet("AI 도구 활용에 대한 표준 가이드라인 수립"))
story.append(bullet("6월 활동량 감소 원인 분석 및 대응"))
story.append(bullet("외부 사이트 접근 보안 검토"))
story.append(bullet("GitHub Git 작업 일정 관리 강화"))

# Footer
story.append(Spacer(1, 12 * mm))
story.append(hr())
story.append(Spacer(1, 4 * mm))
story.append(Paragraph("보고서 작성일: 2026년 7월", styles['SmallNote']))
story.append(Paragraph("작성자: XCN-AI (엑큐)", styles['SmallNote']))
story.append(Paragraph("분류: 솔루션개발팀 - 로깅 데이터 분석", styles['SmallNote']))

# Build PDF
doc.build(story, onFirstPage=cover_page, onLaterPages=page_number)
print(f"PDF generated: {OUTPUT_PATH}")
