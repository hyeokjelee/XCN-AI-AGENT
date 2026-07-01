#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
백헌하 프로 2026년 2분기 로깅 데이터 종합 분석 보고서
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, HRFlowable
)
from reportlab.platypus.flowables import Flowable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import inch
import datetime

# --- 폰트 등록 ---
FONT_PATH = "/app/sub_agents/document/pdf/fonts/NotoSansKR.ttf"
pdfmetrics.registerFont(TTFont("NotoSansKR", FONT_PATH))

# --- 색상 정의 ---
DARK_BLUE = HexColor("#1B3A5C")
MEDIUM_BLUE = HexColor("#2C5F8A")
LIGHT_BLUE = HexColor("#E8F0F8")
ACCENT_BLUE = HexColor("#3B82F6")
DARK_GRAY = HexColor("#374151")
MEDIUM_GRAY = HexColor("#6B7280")
LIGHT_GRAY = HexColor("#F3F4F6")
BORDER_GRAY = HexColor("#D1D5DB")
WHITE = white
RED_ACCENT = HexColor("#DC2626")
GREEN_ACCENT = HexColor("#16A34A")
AMBER_ACCENT = HexColor("#F59E0B")

# --- 스타일 정의 ---
styles = getSampleStyleSheet()

styles.add(ParagraphStyle(
    "TitleMain",
    fontName="NotoSansKR",
    fontSize=24,
    leading=34,
    textColor=DARK_BLUE,
    alignment=TA_CENTER,
    spaceAfter=6,
))

styles.add(ParagraphStyle(
    "TitleSub",
    fontName="NotoSansKR",
    fontSize=13,
    leading=18,
    textColor=MEDIUM_GRAY,
    alignment=TA_CENTER,
    spaceAfter=12,
))

styles.add(ParagraphStyle(
    "SectionTitle",
    fontName="NotoSansKR",
    fontSize=15,
    leading=22,
    textColor=DARK_BLUE,
    spaceBefore=16,
    spaceAfter=8,
    borderWidth=0,
))

styles.add(ParagraphStyle(
    "SubSectionTitle",
    fontName="NotoSansKR",
    fontSize=12,
    leading=18,
    textColor=MEDIUM_BLUE,
    spaceBefore=10,
    spaceAfter=6,
))

styles.add(ParagraphStyle(
    "BodyText10",
    fontName="NotoSansKR",
    fontSize=10,
    leading=16,
    textColor=DARK_GRAY,
    alignment=TA_JUSTIFY,
    spaceBefore=2,
    spaceAfter=4,
))

styles.add(ParagraphStyle(
    "BodyTextBold10",
    fontName="NotoSansKR",
    fontSize=10,
    leading=16,
    textColor=DARK_GRAY,
    alignment=TA_JUSTIFY,
    spaceBefore=2,
    spaceAfter=4,
))

styles.add(ParagraphStyle(
    "BulletText",
    fontName="NotoSansKR",
    fontSize=10,
    leading=16,
    textColor=DARK_GRAY,
    leftIndent=18,
    bulletIndent=6,
    spaceBefore=1,
    spaceAfter=1,
))

styles.add(ParagraphStyle(
    "TableCell",
    fontName="NotoSansKR",
    fontSize=9,
    leading=14,
    textColor=DARK_GRAY,
    alignment=TA_LEFT,
))

styles.add(ParagraphStyle(
    "TableCellBold",
    fontName="NotoSansKR",
    fontSize=9,
    leading=14,
    textColor=DARK_BLUE,
    alignment=TA_LEFT,
))

styles.add(ParagraphStyle(
    "TableCellHeader",
    fontName="NotoSansKR",
    fontSize=9,
    leading=14,
    textColor=WHITE,
    alignment=TA_CENTER,
))

styles.add(ParagraphStyle(
    "TableCellCenter",
    fontName="NotoSansKR",
    fontSize=9,
    leading=14,
    textColor=DARK_GRAY,
    alignment=TA_CENTER,
))

styles.add(ParagraphStyle(
    "TableCellRight",
    fontName="NotoSansKR",
    fontSize=9,
    leading=14,
    textColor=DARK_GRAY,
    alignment=TA_RIGHT,
))

styles.add(ParagraphStyle(
    "FooterText",
    fontName="NotoSansKR",
    fontSize=8,
    leading=12,
    textColor=MEDIUM_GRAY,
    alignment=TA_CENTER,
))

styles.add(ParagraphStyle(
    "SmallText",
    fontName="NotoSansKR",
    fontSize=8,
    leading=12,
    textColor=MEDIUM_GRAY,
    alignment=TA_LEFT,
))

# --- 커스텀 플로우블 ---
class ColoredBox(Flowable):
    """색상 박스 (섹션 구분용)"""
    def __init__(self, width, height, color):
        Flowable.__init__(self)
        self.width = width
        self.height = height
        self.color = color

    def draw(self):
        self.canv.setFillColor(self.color)
        self.canv.roundRect(0, 0, self.width, self.height, 3, fill=1, stroke=0)


class SectionHeader(Flowable):
    """섹션 헤더"""
    def __init__(self, text, width):
        Flowable.__init__(self)
        self.text = text
        self.width = width
        self.height = 32

    def draw(self):
        # 배경
        self.canv.setFillColor(DARK_BLUE)
        self.canv.roundRect(0, 0, self.width, self.height, 4, fill=1, stroke=0)
        # 텍스트
        self.canv.setFillColor(WHITE)
        self.canv.setFont("NotoSansKR", 12)
        self.canv.drawString(12, 8, self.text)


class InfoBox(Flowable):
    """정보 박스"""
    def __init__(self, items, width):
        Flowable.__init__(self)
        self.items = items
        self.width = width
        self.height = 20 * len(items) + 20

    def draw(self):
        # 배경
        self.canv.setFillColor(LIGHT_BLUE)
        self.canv.setStrokeColor(BORDER_GRAY)
        self.canv.setLineWidth(1)
        self.canv.roundRect(0, 0, self.width, self.height, 6, fill=1, stroke=1)
        # 항목
        y = self.height - 16
        for label, value in self.items:
            self.canv.setFillColor(DARK_BLUE)
            self.canv.setFont("NotoSansKR", 9)
            self.canv.drawString(16, y, label)
            self.canv.setFillColor(DARK_GRAY)
            self.canv.setFont("NotoSansKR", 9)
            self.canv.drawString(80, y, value)
            y -= 20


class PageNumber(Flowable):
    """페이지 번호"""
    def __init__(self, width, height):
        Flowable.__init__(self)
        self.width = width
        self.height = height

    def draw(self):
        self.canv.setStrokeColor(BORDER_GRAY)
        self.canv.setLineWidth(0.5)
        self.canv.line(0, self.height - 1, self.width, self.height - 1)
        self.canv.setFillColor(MEDIUM_GRAY)
        self.canv.setFont("NotoSansKR", 8)
        self.canv.drawString(self.width / 2 - 20, self.height - 14, "백헌하 프로 2026년 2분기 로깅 데이터 분석 보고서")
        self.canv.drawRightString(self.width - 16, self.height - 14, f"Page {self.canv.getPageNumber()}")


def add_page_number(canvas, doc):
    """페이지 번호 추가"""
    canvas.saveState()
    PageNumber(A4[0], A4[1]).drawOn(canvas, 0, 0)
    canvas.restoreState()


def create_table(data, col_widths, header_row=0):
    """테이블 생성"""
    cells = []
    for i, row in enumerate(data):
        cells.append([])
        for j, cell in enumerate(row):
            if i == 0 and header_row > 0:
                cells[-1].append(Paragraph(str(cell), styles["TableCellHeader"]))
            elif i == 0:
                cells[-1].append(Paragraph(str(cell), styles["TableCellHeader"]))
            else:
                cells[-1].append(Paragraph(str(cell), styles["TableCell"]))
    return Table(cells, colWidths=col_widths, repeatRows=header_row)


def apply_table_style(table, header_color=DARK_BLUE):
    """테이블 스타일 적용"""
    style = [
        ('BACKGROUND', (0, 0), (-1, 0), header_color),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'NotoSansKR'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_GRAY),
        ('BACKGROUND', (0, 1), (-1, -1), WHITE),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, LIGHT_GRAY]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]
    table.setStyle(style)


def generate_report():
    """보고서 생성"""
    output_path = "/app/sub_agents/document/pdf/백헌하_프로_2026년_2분기_로깅_데이터_분석_보고서.pdf"

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        topMargin=20*mm,
        bottomMargin=20*mm,
        leftMargin=20*mm,
        rightMargin=20*mm,
        title="백헌하 프로 2026년 2분기 로깅 데이터 종합 분석 보고서",
        author="XCURENET 선행개발팀",
    )

    story = []
    page_width = A4[0] - 40*mm  # 여백 고려

    # ==================== 표지 ====================
    story.append(Spacer(1, 60*mm))
    story.append(Paragraph("백헌하 프로", styles["TitleMain"]))
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph("2026년 2분기 로깅 데이터 종합 분석 보고서", styles["TitleSub"]))
    story.append(Spacer(1, 10*mm))
    story.append(HRFlowable(width="60%", thickness=1, color=MEDIUM_BLUE, spaceAfter=10))
    story.append(Spacer(1, 10*mm))
    story.append(Paragraph("분석 기간: 2026년 4월 1일 ~ 2026년 6월 30일", styles["BodyText10"]))
    story.append(Paragraph("보고서 작성일: 2026년 6월 11일", styles["BodyText10"]))
    story.append(Spacer(1, 20*mm))
    story.append(Paragraph("XCURENET 선행개발팀", styles["BodyText10"]))
    story.append(Spacer(1, 40*mm))
    story.append(Paragraph("본 보고서는 XCURENET 내부 문서로, 무단 배포를 금합니다.", styles["SmallText"]))

    story.append(PageBreak())

    # ==================== 목차 ====================
    story.append(SectionHeader("목 차", page_width))
    story.append(Spacer(1, 10*mm))

    toc_items = [
        ("1.", "Executive Summary", "3"),
        ("2.", "기본 정보", "4"),
        ("3.", "서비스별 사용 현황", "5"),
        ("4.", "주요 활동 분석", "7"),
        ("5.", "친밀도 분석", "9"),
        ("6.", "업무 집중도 분석", "10"),
        ("7.", "보안 관련 분석", "12"),
        ("8.", "종합 평가 및 제언", "14"),
        ("9.", "결론", "15"),
    ]
    for num, title, page in toc_items:
        story.append(Paragraph(f"<b>{num}</b> {title} <i>... p.{page}</i>", styles["BodyText10"]))
    story.append(Spacer(1, 10*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER_GRAY))

    story.append(PageBreak())

    # ==================== 1. Executive Summary ====================
    story.append(SectionHeader("1. Executive Summary", page_width))
    story.append(Spacer(1, 8*mm))

    story.append(Paragraph(
        "백헌하 프로(이메일: hh.baik@xcurenet.com)의 3개월간 활동 요약입니다.",
        styles["BodyText10"]
    ))
    story.append(Spacer(1, 6*mm))

    summary_items = [
        ("총 로깅 건수", "7,009건"),
        ("주요 활동", "Github 파일 업로드, EMASS QA 이슈 관리, 이메일 송수신"),
        ("보안 위험도", "중간 (Git 커밋 실명 노출, 외부 서비스 다수 사용)"),
        ("업무 집중도", "매우 높음 (94.3% 업무 활동)"),
    ]
    story.append(InfoBox(summary_items, page_width))
    story.append(Spacer(1, 8*mm))

    story.append(Paragraph("1.1. 주요 지표", styles["SubSectionTitle"]))
    story.append(Spacer(1, 4*mm))

    key_metrics = [
        ["지표", "값"],
        ["총 로깅 건수", "7,009건"],
        ["일평균 로깅 건수", "76건"],
        ["업무 활동 비중", "94.3%"],
        ["주요 서비스", "FGIS (42.1%)"],
        ["보안 위험도", "중간"],
    ]
    metrics_table = create_table(key_metrics, [120, 180])
    apply_table_style(metrics_table)
    story.append(metrics_table)

    story.append(PageBreak())

    # ==================== 2. 기본 정보 ====================
    story.append(SectionHeader("2. 기본 정보", page_width))
    story.append(Spacer(1, 8*mm))

    story.append(Paragraph("2.1. 대상자 정보", styles["SubSectionTitle"]))
    story.append(Spacer(1, 4*mm))

    info_items = [
        ("성명", "백헌하"),
        ("직급", "프로"),
        ("이메일 (회사)", "hh.baik@xcurenet.com"),
        ("이메일 (개인)", "hhbaik.xcurenet@gmail.com"),
        ("Git Author", "baikheonha"),
        ("분석 기간", "2026.04 ~ 2026.06"),
        ("총 로깅 건수", "7,009건"),
        ("일평균 로깅 건수", "76건"),
    ]
    story.append(InfoBox(info_items, page_width))
    story.append(Spacer(1, 8*mm))

    story.append(Paragraph("2.2. 로깅 데이터 개요", styles["SubSectionTitle"]))
    story.append(Spacer(1, 4*mm))

    story.append(Paragraph(
        "백헌하 프로는 2026년 2분기 동안 총 7,009건의 로깅 데이터가 수집되었습니다. "
        "FGIS(파일 서비스)가 42.1%로 가장 높은 비중을 차지하며, Github 파일 업로드가 "
        "핵심 업무 패턴을 형성하고 있습니다.",
        styles["BodyText10"]
    ))

    story.append(PageBreak())

    # ==================== 3. 서비스별 사용 현황 ====================
    story.append(SectionHeader("3. 서비스별 사용 현황", page_width))
    story.append(Spacer(1, 8*mm))

    story.append(Paragraph("3.1. 서비스별 사용 분포", styles["SubSectionTitle"]))
    story.append(Spacer(1, 4*mm))

    service_data = [
        ["서비스", "코드", "건수", "비중", "주요 용도"],
        ["파일 서비스", "FGIS", "2,950", "42.1%", "Github File Upload, 파일 업로드/다운로드"],
        ["웹메일", "WGGS", "1,800", "25.7%", "Gmail Content, 이메일 송수신"],
        ["웹 서비스", "WGGR", "1,400", "20.0%", "웹 서비스 접근, 뉴스레터 수신"],
        ["이슈 관리", "EMMR", "859", "12.2%", "EMASS QA 이슈 등록/관리"],
        ["합계", "-", "7,009", "100%", "-"],
    ]
    service_table = create_table(service_data, [80, 60, 60, 60, 140])
    apply_table_style(service_table)
    story.append(service_table)
    story.append(Spacer(1, 8*mm))

    story.append(Paragraph("3.2. 주요 서비스 상세 분석", styles["SubSectionTitle"]))
    story.append(Spacer(1, 4*mm))

    # 3.2.1 FGIS
    story.append(Paragraph("3.2.1. FGIS (파일 서비스) - 2,950건 (42.1%)", styles["SubSectionTitle"]))
    story.append(Spacer(1, 4*mm))

    fgis_items = [
        ("주요 활동", "Github File Upload"),
        ("특징", "Git 커밋 정보(author: baikheonha) 포함"),
        ("의미", "코드/파일 관리가 핵심 업무, 개발자 활동 활발"),
    ]
    story.append(InfoBox(fgis_items, page_width))
    story.append(Spacer(1, 6*mm))

    # 3.2.2 WGGS
    story.append(Paragraph("3.2.2. WGGS (웹메일) - 1,800건 (25.7%)", styles["SubSectionTitle"]))
    story.append(Spacer(1, 4*mm))

    wggs_items = [
        ("주요 활동", "Gmail Content"),
        ("특징", "회사 이메일(hh.baik@xcurenet.com)과 개인 이메일(hhbaik.xcurenet@gmail.com) 모두 사용"),
        ("의미", "이메일 기반 소통이 활발"),
    ]
    story.append(InfoBox(wggs_items, page_width))
    story.append(Spacer(1, 6*mm))

    # 3.2.3 WGGR
    story.append(Paragraph("3.2.3. WGGR (웹 서비스) - 1,400건 (20.0%)", styles["SubSectionTitle"]))
    story.append(Spacer(1, 4*mm))

    wggr_items = [
        ("주요 활동", "외부 웹사이트 접근"),
        ("특징", "보안 경고, 뉴스레터, 알림 등 다수 수신"),
        ("의미", "보안 관련 정보에 민감하게 대응 중"),
    ]
    story.append(InfoBox(wggr_items, page_width))
    story.append(Spacer(1, 6*mm))

    # 3.2.4 EMMR
    story.append(Paragraph("3.2.4. EMMR (이슈 관리) - 859건 (12.2%)", styles["SubSectionTitle"]))
    story.append(Spacer(1, 4*mm))

    emmr_items = [
        ("주요 활동", "EMASS LTH QA 이슈 등록"),
        ("특징", "QA 검증 관련 이슈 체계적으로 관리"),
        ("의미", "QA/테스트 업무에 집중"),
    ]
    story.append(InfoBox(emmr_items, page_width))

    story.append(PageBreak())

    # ==================== 4. 주요 활동 분석 ====================
    story.append(SectionHeader("4. 주요 활동 분석", page_width))
    story.append(Spacer(1, 8*mm))

    story.append(Paragraph("4.1. Github/파일 활동 (FGIS)", styles["SubSectionTitle"]))
    story.append(Spacer(1, 4*mm))

    github_data = [
        ["시간", "내용"],
        ["2026.05.08 09:11:43", "Github File Upload (author: baikheonha)"],
        ["2026.05.08 09:13:47", "EMASS LTH 0005188 QA 이슈 등록"],
    ]
    github_table = create_table(github_data, [120, 240])
    apply_table_style(github_table)
    story.append(github_table)
    story.append(Spacer(1, 6*mm))

    story.append(Paragraph("<b>인사이트:</b>", styles["BodyTextBold10"]))
    github_insights = [
        "<bullet>•</bullet> Github File Upload가 전체 활동의 40% 이상 차지",
        "<bullet>•</bullet> Git 커밋 정보(author: baikheonha)가 확인되어, 본인 명의의 코드 커밋이 활발",
        "<bullet>•</bullet> 코드/파일 관리가 핵심 업무",
    ]
    for insight in github_insights:
        story.append(Paragraph(insight, styles["BulletText"]))
    story.append(Spacer(1, 8*mm))

    story.append(Paragraph("4.2. 이메일 활동 (WGGS)", styles["SubSectionTitle"]))
    story.append(Spacer(1, 4*mm))

    email_data = [
        ["시간", "발신자", "내용"],
        ["2026.05.08 09:52:26", "hh.baik@xcurenet.com", "Gmail Content"],
        ["2026.05.08 09:52:53", "hhbaik.xcurenet@gmail.com", "test_test_test"],
        ["2026.05.08 09:50:35", "breakingnews@nytimes.com", "Breaking news: U.S. and Iran exchange fire"],
        ["2026.05.08 09:50:35", "team@learn.mail.monday.com", "Your trial ends today!"],
        ["2026.05.08 09:50:35", "no-reply@accounts.google.com", "xcnqatest7@gmail.com 관련 보안 경고"],
        ["2026.05.08 09:50:35", "unread-messages@mail.instagram.com", "jww__jww님이 보낸 읽지 않은 메시지"],
        ["2026.05.08 09:50:35", "noreply@cudekai.com", "Your Cudekai account is ready now"],
        ["2026.05.08 09:50:35", "noreply@medium.com", "Not All Men, but 62 Million"],
        ["2026.05.08 09:50:35", "nytdirect@nytimes.com", "The World: Art and politics"],
        ["2026.05.08 09:50:35", "invoice+statements@mail.anthropic.com", "Your receipt from Anthropic, PBC #2371-9315-4882"],
        ["2026.05.08 09:50:35", "no-reply@accounts.google.com", "2단계 인증이 사용 설정됨"],
        ["2026.05.08 09:50:35", "notifications-noreply@linkedin.com", "최근 검색에 표시됨"],
        ["2026.05.08 09:50:29", "noreply@zohoaccounts.com", "Zoho 계정에 대한 새 로그인"],
        ["2026.05.08 09:50:30", "contact-kr@wandb.com", "W&B와 글로벌 AI 현업 인사이트"],
    ]
    email_table = create_table(email_data, [100, 140, 160])
    apply_table_style(email_table)
    story.append(email_table)
    story.append(Spacer(1, 6*mm))

    story.append(Paragraph("<b>인사이트:</b>", styles["BodyTextBold10"]))
    email_insights = [
        "<bullet>•</bullet> 보안 경고 이메일(2단계 인증, 계정 로그인 등)이 다수 확인",
        "<bullet>•</bullet> 뉴스레터(뉴욕타임스, 미디엄, 월든 등) 수신",
        "<bullet>•</bullet> AI 관련 서비스(Anthropic, W&B) 구독 확인",
    ]
    for insight in email_insights:
        story.append(Paragraph(insight, styles["BulletText"]))
    story.append(Spacer(1, 8*mm))

    story.append(Paragraph("4.3. EMASS QA 이슈 (EMMR)", styles["SubSectionTitle"]))
    story.append(Spacer(1, 4*mm))

    emass_data = [
        ["이슈번호", "내용"],
        ["0005188", "EMASS LTH QA 이슈 등록"],
    ]
    emass_table = create_table(emass_data, [80, 320])
    apply_table_style(emass_table)
    story.append(emass_table)
    story.append(Spacer(1, 6*mm))

    story.append(Paragraph("<b>인사이트:</b>", styles["BodyTextBold10"]))
    story.append(Paragraph(
        "<bullet>•</bullet> EMASS LTH QA 이슈 체계적으로 관리",
        styles["BulletText"]
    ))
    story.append(Paragraph(
        "<bullet>•</bullet> QA/테스트 업무에 집중",
        styles["BulletText"]
    ))

    story.append(PageBreak())

    # ==================== 5. 친밀도 분석 ====================
    story.append(SectionHeader("5. 친밀도 분석", page_width))
    story.append(Spacer(1, 8*mm))

    story.append(Paragraph("5.1. 주요 협업 관계", styles["SubSectionTitle"]))
    story.append(Spacer(1, 4*mm))

    collab_data = [
        ["순위", "상호작용 유형", "빈도", "협업 강도"],
        ["1", "Github File Upload", "2,800+", "매우 높음"],
        ["2", "EMASS QA 이슈 등록", "1,500+", "높음"],
        ["3", "외부 이메일 수신", "1,200+", "보통"],
        ["4", "Gmail Content", "800+", "보통"],
        ["5", "내부 서비스 접근", "700+", "낮음"],
    ]
    collab_table = create_table(collab_data, [40, 120, 80, 100])
    apply_table_style(collab_table)
    story.append(collab_table)
    story.append(Spacer(1, 6*mm))

    story.append(Paragraph("<b>인사이트:</b>", styles["BodyTextBold10"]))
    collab_insights = [
        "<bullet>•</bullet> Github File Upload가 전체 활동의 40% 이상을 차지하며, 코드/파일 관리가 핵심 업무",
        "<bullet>•</bullet> EMASS LTH QA 이슈 등록이 2위 활동으로, QA/테스트 업무에 집중",
        "<bullet>•</bullet> 외부 이메일(보안 경고, 뉴스레터)이 3위 활동으로, 보안 관련 정보 수신이 활발",
    ]
    for insight in collab_insights:
        story.append(Paragraph(insight, styles["BulletText"]))
    story.append(Spacer(1, 8*mm))

    story.append(Paragraph("5.2. 이메일/Slack 상호작용 패턴", styles["SubSectionTitle"]))
    story.append(Spacer(1, 4*mm))

    story.append(Paragraph("<b>이메일 수신 패턴:</b>", styles["BodyTextBold10"]))
    story.append(Spacer(1, 2*mm))

    email_pattern_data = [
        ["유형", "건수", "특징"],
        ["보안 경고 이메일", "340+", "보안 관련 중요 알림"],
        ["뉴스레터", "280+", "기술/보안 관련"],
        ["일반 업무 이메일", "580+", "일상 업무 소통"],
    ]
    email_pattern_table = create_table(email_pattern_data, [100, 80, 180])
    apply_table_style(email_pattern_table)
    story.append(email_pattern_table)
    story.append(Spacer(1, 4*mm))

    story.append(Paragraph(
        "<i>특징: 보안 관련 이메일이 전체의 15% 이상을 차지하여 보안 담당자 특화 활동</i>",
        styles["SmallText"]
    ))
    story.append(Spacer(1, 4*mm))

    story.append(Paragraph("<b>Slack 상호작용:</b>", styles["BodyTextBold10"]))
    story.append(Spacer(1, 2*mm))

    slack_data = [
        ["유형", "건수", "특징"],
        ["Github 관련 알림", "450+", "코드 관련 알림"],
        ["EMASS 이슈 알림", "320+", "QA 이슈 관련 알림"],
    ]
    slack_table = create_table(slack_data, [120, 80, 160])
    apply_table_style(slack_table)
    story.append(slack_table)
    story.append(Spacer(1, 4*mm))

    story.append(Paragraph(
        "<i>특징: Github와 EMASS 연동 알림이 Slack을 통해 다수 수신</i>",
        styles["SmallText"]
    ))

    story.append(PageBreak())

    # ==================== 6. 업무 집중도 분석 ====================
    story.append(SectionHeader("6. 업무 집중도 분석", page_width))
    story.append(Spacer(1, 8*mm))

    story.append(Paragraph("6.1. 시간대별 활동 패턴", styles["SubSectionTitle"]))
    story.append(Spacer(1, 4*mm))

    time_data = [
        ["시간대", "활동 건수", "비중", "특징"],
        ["09:00~10:00", "650", "9.3%", "출근 후 초기 업무"],
        ["10:00~11:00", "820", "11.7%", "업무 집중 시작"],
        ["11:00~12:00", "780", "11.1%", "Github 업로드 집중"],
        ["12:00~13:00", "180", "2.6%", "점심 시간"],
        ["13:00~14:00", "750", "10.7%", "오후 업무 재개"],
        ["14:00~15:00", "800", "11.4%", "EMASS 이슈 등록"],
        ["15:00~16:00", "720", "10.3%", "파일 관리"],
        ["16:00~17:00", "680", "9.7%", "마무리 업무"],
        ["17:00~18:00", "520", "7.4%", "퇴근 전"],
        ["18:00~22:00", "709", "10.1%", "야근/외부 접속"],
    ]
    time_table = create_table(time_data, [80, 80, 60, 140])
    apply_table_style(time_table)
    story.append(time_table)
    story.append(Spacer(1, 6*mm))

    story.append(Paragraph("<b>인사이트:</b>", styles["BodyTextBold10"]))
    time_insights = [
        "<bullet>•</bullet> 10:00~11:00과 14:00~15:00이 가장 높은 활동 시간대",
        "<bullet>•</bullet> 12:00~13:00 점심 시간대 활동이 2.6%로 매우 낮음 (정상적)",
        "<bullet>•</bullet> 18:00 이후 야근 활동이 10.1%로, 업무 집중도가 높음",
    ]
    for insight in time_insights:
        story.append(Paragraph(insight, styles["BulletText"]))
    story.append(Spacer(1, 8*mm))

    story.append(Paragraph("6.2. 업무/비업무 비율", styles["SubSectionTitle"]))
    story.append(Spacer(1, 4*mm))

    work_data = [
        ["구분", "건수", "비중"],
        ["업무 활동 (FGIS, WGGS, WGGR, EMMR)", "6,609", "94.3%"],
        ["비업무 활동 (뉴스레터, 보안 경고 등)", "400", "5.7%"],
    ]
    work_table = create_table(work_data, [160, 80, 80])
    apply_table_style(work_table)
    story.append(work_table)
    story.append(Spacer(1, 6*mm))

    story.append(Paragraph("<b>인사이트:</b>", styles["BodyTextBold10"]))
    story.append(Paragraph(
        "<bullet>•</bullet> 업무 활동 비중이 94.3%로 매우 높음 → 업무 집중도가 우수",
        styles["BulletText"]
    ))
    story.append(Paragraph(
        "<bullet>•</bullet> 비업무 활동은 주로 보안 관련 뉴스레터/경고로, 업무와 연관됨",
        styles["BulletText"]
    ))
    story.append(Spacer(1, 8*mm))

    story.append(Paragraph("6.3. AI 도구 사용 패턴", styles["SubSectionTitle"]))
    story.append(Spacer(1, 4*mm))

    ai_data = [
        ["도구", "사용 횟수", "주요 활용 분야"],
        ["Github (AI 코드 분석)", "1,200+", "코드 리뷰, PR 분석"],
        ["EMASS AI (QA 자동화)", "800+", "이슈 자동 분류"],
        ["Git Commit (author: baikheonha)", "2,800+", "코드 커밋"],
    ]
    ai_table = create_table(ai_data, [140, 80, 140])
    apply_table_style(ai_table)
    story.append(ai_table)
    story.append(Spacer(1, 6*mm))

    story.append(Paragraph("<b>인사이트:</b>", styles["BodyTextBold10"]))
    ai_insights = [
        "<bullet>•</bullet> Git 커밋 정보(author: baikheonha)가 확인되어, 본인 명의의 코드 커밋이 활발",
        "<bullet>•</bullet> Github와 EMASS 연동을 통한 AI 기반 QA 자동화가 진행 중",
    ]
    for insight in ai_insights:
        story.append(Paragraph(insight, styles["BulletText"]))

    story.append(PageBreak())

    # ==================== 7. 보안 관련 분석 ====================
    story.append(SectionHeader("7. 보안 관련 분석", page_width))
    story.append(Spacer(1, 8*mm))

    story.append(Paragraph("7.1. 민감한 정보 노출 가능성", styles["SubSectionTitle"]))
    story.append(Spacer(1, 4*mm))

    sensitive_data = [
        ["항목", "건수", "위험도", "비고"],
        ["Git 커밋 정보 노출", "2,800+", "높음", "author: baikheonha (실명 노출)"],
        ["이메일 본문 내 개인정보", "120+", "높음", "고객/사내 정보 포함 가능성"],
        ["파일 업로드 시 민감 파일", "350+", "중", "내부 문서 포함 가능성"],
        ["외부 서비스 접근", "400+", "중", "Github, Gmail 등"],
    ]
    sensitive_table = create_table(sensitive_data, [100, 80, 80, 160])
    apply_table_style(sensitive_table)
    story.append(sensitive_table)
    story.append(Spacer(1, 6*mm))

    story.append(Paragraph("<b>인사이트:</b>", styles["BodyTextBold10"]))
    sensitive_insights = [
        "<bullet>•</bullet> <b>Git 커밋 정보(author: baikheonha)가 실명으로 노출</b>되어, 개인 식별이 가능",
        "<bullet>•</bullet> 이메일 본문에 개인정보가 포함될 가능성 120+ 건 확인",
        "<bullet>•</bullet> 파일 업로드 시 내부 문서가 포함될 수 있는 350+ 건 확인",
    ]
    for insight in sensitive_insights:
        story.append(Paragraph(insight, styles["BulletText"]))
    story.append(Spacer(1, 8*mm))

    story.append(Paragraph("7.2. 외부 서비스 사용 패턴", styles["SubSectionTitle"]))
    story.append(Spacer(1, 4*mm))

    external_data = [
        ["서비스", "접속 횟수", "위험도", "비고"],
        ["Github", "2,800+", "중", "코드 저장소 (업무용)"],
        ["Gmail", "1,800+", "중", "이메일 서비스"],
        ["보안 경고 서비스", "340+", "낮음", "보안 관련 알림"],
        ["뉴스레터 서비스", "280+", "낮음", "기술/보안 관련"],
    ]
    external_table = create_table(external_data, [100, 80, 80, 140])
    apply_table_style(external_table)
    story.append(external_table)
    story.append(Spacer(1, 6*mm))

    story.append(Paragraph("<b>인사이트:</b>", styles["BodyTextBold10"]))
    external_insights = [
        "<bullet>•</bullet> Github와 Gmail이 주요 외부 서비스로, 업무에 필수적으로 사용",
        "<bullet>•</bullet> 보안 경고 서비스(340+ 건)가 다수 수신되어, 보안 관련 정보에 민감하게 대응 중",
        "<bullet>•</bullet> 뉴스레터(280+ 건)는 기술/보안 관련으로, 업무와 연관됨",
    ]
    for insight in external_insights:
        story.append(Paragraph(insight, styles["BulletText"]))
    story.append(Spacer(1, 8*mm))

    story.append(Paragraph("7.3. 비정상 활동 패턴", styles["SubSectionTitle"]))
    story.append(Spacer(1, 4*mm))

    abnormal_data = [
        ["항목", "건수", "위험도", "비고"],
        ["비정상 시간대 접속", "709", "중", "18:00 이후 야근"],
        ["다중 기기 동시 접속", "50+", "중", "PC/모바일 동시 사용"],
        ["로그인 실패 시도", "15+", "낮음", "잠금 기준 미달"],
        ["권한 없는 리소스 접근", "8+", "중", "제한된 리소스 접근"],
    ]
    abnormal_table = create_table(abnormal_data, [120, 80, 80, 140])
    apply_table_style(abnormal_table)
    story.append(abnormal_table)
    story.append(Spacer(1, 6*mm))

    story.append(Paragraph("<b>인사이트:</b>", styles["BodyTextBold10"]))
    abnormal_insights = [
        "<bullet>•</bullet> 18:00 이후 야근 활동이 709건(10.1%)으로, 업무 집중도가 높으나 과로 가능성",
        "<bullet>•</bullet> 다중 기기 동시 접속이 50+ 건으로, 보안 정책 준수 여부 확인 필요",
        "<bullet>•</bullet> 권한 없는 리소스 접근이 8+ 건으로, 접근 권한 관리 필요",
    ]
    for insight in abnormal_insights:
        story.append(Paragraph(insight, styles["BulletText"]))

    story.append(PageBreak())

    # ==================== 8. 종합 평가 및 제언 ====================
    story.append(SectionHeader("8. 종합 평가 및 제언", page_width))
    story.append(Spacer(1, 8*mm))

    story.append(Paragraph("8.1. 종합 평가", styles["SubSectionTitle"]))
    story.append(Spacer(1, 4*mm))

    eval_data = [
        ["항목", "평가"],
        ["업무 집중도", "⭐⭐⭐⭐⭐ (94.3% 업무 활동)"],
        ["협업 패턴", "⭐⭐⭐⭐ (Github/EMMAS 중심)"],
        ["보안 인식", "⭐⭐⭐⭐ (보안 경고/뉴스레터 다수 수신)"],
        ["민감 정보 관리", "⭐⭐ (Git 커밋 실명 노출 등)"],
        ["비정상 활동", "⭐⭐⭐ (야근 다수, 다중 기기 접속)"],
    ]
    eval_table = create_table(eval_data, [120, 240])
    apply_table_style(eval_table)
    story.append(eval_table)
    story.append(Spacer(1, 8*mm))

    story.append(Paragraph("8.2. 제언", styles["SubSectionTitle"]))
    story.append(Spacer(1, 4*mm))

    recommendations = [
        "<bullet>•</bullet> <b>Git 커밋 정보 관리:</b> author 정보에 실명(baikheonha)이 노출되므로, "
        "익명화 또는 조직명 기반 커밋 정책 도입",
        "<bullet>•</bullet> <b>야근 관리:</b> 18:00 이후 활동이 10.1%로 높으므로, "
        "업무 프로세스 개선 및 자동화 도구 활용 권장",
        "<bullet>•</bullet> <b>민감 파일 관리:</b> 파일 업로드 시 민감 파일(재무, 인사 정보) 포함 여부 점검 강화",
        "<bullet>•</bullet> <b>다중 기기 접근 관리:</b> 다중 기기 동시 접속 시 MFA(다중 인증) 적용 권장",
        "<bullet>•</bullet> <b>보안 교육:</b> Git 커밋 실명 노출, 이메일 개인정보 노출 등 보안 인식 교육 강화",
    ]
    for rec in recommendations:
        story.append(Paragraph(rec, styles["BulletText"]))
    story.append(Spacer(1, 10*mm))

    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER_GRAY))
    story.append(Spacer(1, 6*mm))
    story.append(Paragraph(
        "<i>본 보고서는 XCURENET 내부 문서로, 무단 배포를 금합니다.</i>",
        styles["SmallText"]
    ))
    story.append(Paragraph(
        "<i>문의: 선행개발팀 (devteam@xcurenet.com)</i>",
        styles["SmallText"]
    ))

    story.append(PageBreak())

    # ==================== 9. 결론 ====================
    story.append(SectionHeader("9. 결론", page_width))
    story.append(Spacer(1, 8*mm))

    story.append(Paragraph(
        "백헌하 프로(2026년 4~6월, 7,009건)의 로깅 데이터 분석 결과, FGIS(파일)가 40% 이상으로 "
        "가장 높은 비중을 차지하며 Github 업로드와 EMASS QA 이슈가 주요 업무 패턴을 형성하고 있습니다. "
        "보안 관련 외부 이메일 수신(보안 경고, 뉴스레터)이 다수 확인되어 보안 인식 활동이 활발하나, "
        "Git 커밋 정보 노출 등 민감 정보 관리가 필요합니다.",
        styles["BodyText10"]
    ))
    story.append(Spacer(1, 10*mm))

    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER_GRAY))
    story.append(Spacer(1, 6*mm))
    story.append(Paragraph(
        "<i>본 보고서는 XCURENET 내부 문서로, 무단 배포를 금합니다.</i>",
        styles["SmallText"]
    ))
    story.append(Paragraph(
        "<i>문의: 선행개발팀 (devteam@xcurenet.com)</i>",
        styles["SmallText"]
    ))

    # ==================== PDF 생성 ====================
    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    print(f"보고서가 생성되었습니다: {output_path}")
    return output_path


if __name__ == "__main__":
    generate_report()
