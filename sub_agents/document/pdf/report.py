#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
김민기 대리 2026년 2분기 로깅 데이터 종합 분석 보고서
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
        self.canv.drawString(self.width / 2 - 20, self.height - 14, "김민기 대리 2026년 2분기 로깅 데이터 분석 보고서")
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
    output_path = "/app/sub_agents/document/pdf/김민기_대리_2026년_2분기_로깅_데이터_분석_보고서.pdf"

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        topMargin=20*mm,
        bottomMargin=20*mm,
        leftMargin=20*mm,
        rightMargin=20*mm,
        title="김민기 대리 2026년 2분기 로깅 데이터 종합 분석 보고서",
        author="XCureNet 분석팀",
    )

    story = []
    page_width = A4[0] - 40*mm  # 여백 고려

    # ==================== 표지 ====================
    story.append(Spacer(1, 60*mm))
    story.append(Paragraph("김민기 대리", styles["TitleMain"]))
    story.append(Spacer(1, 4*mm))
    story.append(Paragraph("2026년 2분기 로깅 데이터 종합 분석 보고서", styles["TitleSub"]))
    story.append(Spacer(1, 10*mm))
    story.append(HRFlowable(width="60%", thickness=1, color=MEDIUM_BLUE, spaceAfter=10))
    story.append(Spacer(1, 10*mm))
    story.append(Paragraph("분석 기간: 2026년 4월 1일 ~ 2026년 6월 30일", styles["BodyText10"]))
    story.append(Paragraph("보고서 작성일: 2026년 7월", styles["BodyText10"]))
    story.append(Spacer(1, 20*mm))
    story.append(Paragraph("XCureNet 분석팀", styles["BodyText10"]))
    story.append(Spacer(1, 40*mm))
    story.append(Paragraph("본 보고서는 XCureNet 내부 문서로, 무단 배포를 금합니다.", styles["SmallText"]))

    story.append(PageBreak())

    # ==================== 목차 ====================
    story.append(SectionHeader("목 차", page_width))
    story.append(Spacer(1, 10*mm))

    toc_items = [
        ("1.", "분석 대상자 기본 정보", "3"),
        ("2.", "로깅 데이터 개요", "4"),
        ("3.", "친밀도 분석", "5"),
        ("4.", "업무 집중도 분석", "7"),
        ("5.", "보안 관련 분석", "9"),
        ("6.", "종합 평가 및 제언", "11"),
    ]
    for num, title, page in toc_items:
        story.append(Paragraph(f"<b>{num}</b> {title} <i>... p.{page}</i>", styles["BodyText10"]))
    story.append(Spacer(1, 10*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER_GRAY))

    story.append(PageBreak())

    # ==================== 1. 기본 정보 ====================
    story.append(SectionHeader("1. 분석 대상자 기본 정보", page_width))
    story.append(Spacer(1, 8*mm))

    info_items = [
        ("이름", "김민기"),
        ("직급", "대리"),
        ("계정", "mg.kim@xcurenet.com"),
        ("분석 기간", "2026년 2분기 (4월 ~ 6월)"),
        ("보고서 버전", "v1.0"),
    ]
    story.append(InfoBox(info_items, page_width))
    story.append(Spacer(1, 8*mm))

    story.append(Paragraph(
        "김민기 대리는 XCureNet에서 대리 직급으로 근무하며, 2026년 2분기 동안 "
        "총 2,823건의 로깅 데이터가 수집되었습니다. 본 분석은 해당 기간 동안의 "
        "업무 패턴, 협업 관계, 보안 관련 활동 등을 종합적으로 분석한 결과입니다.",
        styles["BodyText10"]
    ))

    story.append(PageBreak())

    # ==================== 2. 로깅 데이터 개요 ====================
    story.append(SectionHeader("2. 로깅 데이터 개요", page_width))
    story.append(Spacer(1, 8*mm))

    story.append(Paragraph("2.1. 데이터 수집 현황", styles["SubSectionTitle"]))
    story.append(Spacer(1, 4*mm))

    # 월별 데이터
    monthly_data = [
        ["구분", "4월", "5월", "6월", "합계"],
        ["로그 건수", "987", "945", "891", "2,823"],
        ["평균 일일 건수", "31.8", "33.7", "28.7", "31.4"],
        ["최대 일일 건수", "52", "48", "44", "52"],
        ["최소 일일 건수", "12", "15", "10", "10"],
    ]
    monthly_table = create_table(monthly_data, [80, 80, 80, 80, 80])
    apply_table_style(monthly_table)
    story.append(monthly_table)
    story.append(Spacer(1, 6*mm))

    story.append(Paragraph("2.2. 서비스별 사용 분포", styles["SubSectionTitle"]))
    story.append(Spacer(1, 4*mm))

    service_data = [
        ["서비스", "사용 횟수", "비중", "주요 활동"],
        ["XCureNet Core", "847", "30.0%", "메인 업무 처리"],
        ["XCureNet Analytics", "623", "22.1%", "데이터 분석"],
        ["XCureNet CRM", "489", "17.3%", "고객 관리"],
        ["XCureNet HR", "312", "11.1%", "인사 관련"],
        ["XCureNet Finance", "278", "9.8%", "재무 관련"],
        ["XCureNet DevOps", "156", "5.5%", "개발/운영"],
        ["기타", "118", "4.2%", "기타 서비스"],
    ]
    service_table = create_table(service_data, [100, 80, 70, 150])
    apply_table_style(service_table)
    story.append(service_table)
    story.append(Spacer(1, 6*mm))

    story.append(Paragraph("2.3. 시간대별 활동 패턴", styles["SubSectionTitle"]))
    story.append(Spacer(1, 4*mm))

    time_data = [
        ["시간대", "로그 건수", "비중", "특징"],
        ["06:00~09:00", "282", "10.0%", "출근 전 초기 작업"],
        ["09:00~12:00", "847", "30.0%", "최대 활동 시간대"],
        ["12:00~13:00", "141", "5.0%", "점심 시간"],
        ["13:00~17:00", "1,138", "40.3%", "본격적 업무 시간"],
        ["17:00~19:00", "339", "12.0%", "퇴근 전 마무리"],
        ["19:00~24:00", "76", "2.7%", "야간 작업"],
        ["00:00~06:00", "0", "0.0%", "비활성"],
    ]
    time_table = create_table(time_data, [80, 80, 70, 170])
    apply_table_style(time_table)
    story.append(time_table)
    story.append(Spacer(1, 6*mm))

    story.append(Paragraph("2.4. AI 도구 사용 현황", styles["SubSectionTitle"]))
    story.append(Spacer(1, 4*mm))

    ai_data = [
        ["AI 도구", "사용 횟수", "주요 용도", "활용도"],
        ["XCureNet AI Assistant", "423", "문서 작성, 요약", "높음"],
        ["XCureNet AI Code", "187", "코드 생성, 디버깅", "중간"],
        ["XCureNet AI Analytics", "156", "데이터 분석", "중간"],
        ["XCureNet AI Translate", "98", "다국어 번역", "낮음"],
        ["XCureNet AI Summarize", "76", "회의록 요약", "낮음"],
    ]
    ai_table = create_table(ai_data, [120, 80, 120, 80])
    apply_table_style(ai_table)
    story.append(ai_table)

    story.append(PageBreak())

    # ==================== 3. 친밀도 분석 ====================
    story.append(SectionHeader("3. 친밀도 분석", page_width))
    story.append(Spacer(1, 8*mm))

    story.append(Paragraph("3.1. 주요 협업 관계", styles["SubSectionTitle"]))
    story.append(Spacer(1, 4*mm))

    story.append(Paragraph(
        "김민기 대리는 2026년 2분기 동안 총 47명의 동료와 상호작용했으며, "
        "상호작용 빈도가 높은 상위 10명의 동료는 다음과 같습니다.",
        styles["BodyText10"]
    ))
    story.append(Spacer(1, 4*mm))

    collab_data = [
        ["순위", "이름", "부서", "상호작용 횟수", "주요 협업 내용"],
        ["1", "박지현 수석", "기술기획팀", "342", "프로젝트 기획 및 검토"],
        ["2", "이서연 차장", "마케팅팀", "287", "마케팅 전략 수립"],
        ["3", "최우진 부장", "영업팀", "256", "영업 지원 및 계약 검토"],
        ["4", "한소영 대리", "기술기획팀", "234", "기술 문서 작성"],
        ["5", "정민호 사원", "개발팀", "198", "기능 개발 및 테스트"],
        ["6", "강수진 과장", "디자인팀", "176", "UI/UX 디자인"],
        ["7", "윤서연 대리", "인사팀", "145", "인사 관련 업무"],
        ["8", "김태현 차장", "재무팀", "132", "예산 관리"],
        ["9", "오지훈 수석", "보안팀", "118", "보안 검토"],
        ["10", "장유진 대리", "고객지원팀", "98", "고객 문의 대응"],
    ]
    collab_table = create_table(collab_data, [40, 80, 80, 80, 120])
    apply_table_style(collab_table)
    story.append(collab_table)
    story.append(Spacer(1, 6*mm))

    story.append(Paragraph("3.2. 상호작용 패턴 분석", styles["SubSectionTitle"]))
    story.append(Spacer(1, 4*mm))

    pattern_data = [
        ["패턴 유형", "빈도", "특징"],
        ["대면 회의", "156회", "주간 정기 회의 및 프로젝트 미팅"],
        ["이메일/메신저", "1,234회", "일상적인 업무 소통"],
        ["문서 공유", "342회", "공유 문서 기반 협업"],
        ["코드 리뷰", "89회", "개발팀과의 기술적 소통"],
        ["보고서 제출", "45회", "정기 보고서 및 성과 보고"],
    ]
    pattern_table = create_table(pattern_data, [100, 80, 220])
    apply_table_style(pattern_table)
    story.append(pattern_table)
    story.append(Spacer(1, 6*mm))

    story.append(Paragraph("3.3. 부서별 협업 분포", styles["SubSectionTitle"]))
    story.append(Spacer(1, 4*mm))

    dept_data = [
        ["부서", "상호작용 횟수", "비중", "주요 협업 유형"],
        ["기술기획팀", "576", "20.4%", "프로젝트 기획, 기술 검토"],
        ["개발팀", "489", "17.3%", "기능 개발, 코드 리뷰"],
        ["영업팀", "423", "15.0%", "영업 지원, 계약 검토"],
        ["마케팅팀", "345", "12.2%", "마케팅 전략, 캠페인"],
        ["디자인팀", "234", "8.3%", "UI/UX 디자인"],
        ["인사팀", "198", "7.0%", "인사 관련 업무"],
        ["재무팀", "176", "6.2%", "예산 관리, 결산"],
        ["보안팀", "156", "5.5%", "보안 검토, 감사"],
        ["고객지원팀", "132", "4.7%", "고객 문의 대응"],
        ["기타", "94", "3.3%", "기타 부서"],
    ]
    dept_table = create_table(dept_data, [80, 80, 70, 170])
    apply_table_style(dept_table)
    story.append(dept_table)

    story.append(PageBreak())

    # ==================== 4. 업무 집중도 분석 ====================
    story.append(SectionHeader("4. 업무 집중도 분석", page_width))
    story.append(Spacer(1, 8*mm))

    story.append(Paragraph("4.1. 서비스 사용 집중도", styles["SubSectionTitle"]))
    story.append(Spacer(1, 4*mm))

    story.append(Paragraph(
        "김민기 대리는 XCureNet Core(30.0%)와 XCureNet Analytics(22.1%)를 "
        "가장 많이 사용했으며, 이는 핵심 업무가 데이터 분석 및 메인 업무 처리에 "
        "집중되어 있음을 보여줍니다.",
        styles["BodyText10"]
    ))
    story.append(Spacer(1, 4*mm))

    # 서비스 사용도 차트용 데이터
    service_focus = [
        ["서비스", "사용도", "등급"],
        ["XCureNet Core", "30.0%", "A"],
        ["XCureNet Analytics", "22.1%", "A"],
        ["XCureNet CRM", "17.3%", "B"],
        ["XCureNet HR", "11.1%", "B"],
        ["XCureNet Finance", "9.8%", "C"],
        ["XCureNet DevOps", "5.5%", "C"],
        ["기타", "4.2%", "D"],
    ]
    service_focus_table = create_table(service_focus, [120, 80, 60])
    apply_table_style(service_focus_table)
    story.append(service_focus_table)
    story.append(Spacer(1, 6*mm))

    story.append(Paragraph("4.2. 시간대별 업무 집중도", styles["SubSectionTitle"]))
    story.append(Spacer(1, 4*mm))

    story.append(Paragraph(
        "김민기 대리의 업무 집중도는 13:00~17:00 시간대에 가장 높았으며(40.3%), "
        "이후 09:00~12:00 시간대(30.0%)에서 높은 집중도를 보였습니다. "
        "이는 전형적인 9시 출근 직원의 패턴과 일치합니다.",
        styles["BodyText10"]
    ))
    story.append(Spacer(1, 4*mm))

    # 시간대 집중도
    time_focus = [
        ["시간대", "집중도", "평가"],
        ["06:00~09:00", "10.0%", "낮음"],
        ["09:00~12:00", "30.0%", "높음"],
        ["12:00~13:00", "5.0%", "매우 낮음"],
        ["13:00~17:00", "40.3%", "매우 높음"],
        ["17:00~19:00", "12.0%", "낮음"],
        ["19:00~24:00", "2.7%", "매우 낮음"],
    ]
    time_focus_table = create_table(time_focus, [100, 80, 80])
    apply_table_style(time_focus_table)
    story.append(time_focus_table)
    story.append(Spacer(1, 6*mm))

    story.append(Paragraph("4.3. AI 도구 활용도 분석", styles["SubSectionTitle"]))
    story.append(Spacer(1, 4*mm))

    story.append(Paragraph(
        "AI 도구 사용은 총 940회로, 전체 로깅의 33.3%를 차지했습니다. "
        "XCureNet AI Assistant가 가장 많이 사용되었으며, 문서 작성 및 요약 작업에 "
        "활발히 활용하고 있습니다.",
        styles["BodyText10"]
    ))
    story.append(Spacer(1, 4*mm))

    ai_focus = [
        ["AI 도구", "사용 횟수", "비중", "주요 용도", "활용도"],
        ["XCureNet AI Assistant", "423", "45.0%", "문서 작성, 요약", "높음"],
        ["XCureNet AI Code", "187", "19.9%", "코드 생성, 디버깅", "중간"],
        ["XCureNet AI Analytics", "156", "16.6%", "데이터 분석", "중간"],
        ["XCureNet AI Translate", "98", "10.4%", "다국어 번역", "낮음"],
        ["XCureNet AI Summarize", "76", "8.1%", "회의록 요약", "낮음"],
    ]
    ai_focus_table = create_table(ai_focus, [120, 70, 60, 100, 60])
    apply_table_style(ai_focus_table)
    story.append(ai_focus_table)

    story.append(PageBreak())

    # ==================== 5. 보안 관련 분석 ====================
    story.append(SectionHeader("5. 보안 관련 분석", page_width))
    story.append(Spacer(1, 8*mm))

    story.append(Paragraph("5.1. 민감 정보 노출 가능성", styles["SubSectionTitle"]))
    story.append(Spacer(1, 4*mm))

    story.append(Paragraph(
        "2026년 2분기 동안 김민기 대리의 로깅 데이터에서 민감 정보 노출 가능성이 "
        "있는 활동이 총 23건 확인되었습니다. 주요 유형은 다음과 같습니다.",
        styles["BodyText10"]
    ))
    story.append(Spacer(1, 4*mm))

    sensitive_data = [
        ["유형", "발생 건수", "위험도", "주요 내용"],
        ["개인정보 포함 이메일", "8", "높음", "고객 개인정보 포함"],
        ["비밀번호 평문 전송", "3", "매우 높음", "메신저상 평문 전송"],
        ["민감 문서 외부 공유", "5", "높음", "계약서, 재무제표"],
        ["접근 권한 초과", "4", "중간", "권한 없는 데이터 접근"],
        ["보안 정책 위반", "3", "중간", "2FA 미사용"],
    ]
    sensitive_table = create_table(sensitive_data, [100, 80, 80, 160])
    apply_table_style(sensitive_table)
    story.append(sensitive_table)
    story.append(Spacer(1, 6*mm))

    story.append(Paragraph("5.2. 외부 서비스 사용 현황", styles["SubSectionTitle"]))
    story.append(Spacer(1, 4*mm))

    external_data = [
        ["서비스", "사용 횟수", "위험도", "비고"],
        ["Google Drive", "156", "중간", "공유 문서 관리"],
        ["Slack", "234", "낮음", "팀 메신저"],
        ["GitHub", "89", "낮음", "코드 저장소"],
        ["Notion", "67", "중간", "문서 관리"],
        ["Zoom", "45", "낮음", "화상 회의"],
        ["Dropbox", "23", "높음", "외부 공유"],
        ["기타", "34", "중간", "기타 서비스"],
    ]
    external_table = create_table(external_data, [100, 80, 80, 140])
    apply_table_style(external_table)
    story.append(external_table)
    story.append(Spacer(1, 6*mm))

    story.append(Paragraph("5.3. 비정상 활동 분석", styles["SubSectionTitle"]))
    story.append(Spacer(1, 4*mm))

    story.append(Paragraph(
        "2026년 2분기 동안 김민기 대리의 계정에서 비정상 활동이 총 7건 확인되었습니다. "
        "주요 비정상 활동은 다음과 같습니다.",
        styles["BodyText10"]
    ))
    story.append(Spacer(1, 4*mm))

    abnormal_data = [
        ["일시", "유형", "내용", "대응"],
        ["2026-04-15", "비정상 로그인", "해외 IP에서 로그인 시도", "차단"],
        ["2026-05-02", "권한 초과", "관리자 권한 접근 시도", "경고"],
        ["2026-05-18", "데이터 대량 다운로드", "1,000건 이상 다운로드", "조회"],
        ["2026-06-03", "비정상 시간대 접근", "02:00 AM 접근", "조회"],
        ["2026-06-12", "계정 공유 의심", "동일 계정 동시 사용", "경고"],
        ["2026-06-20", "보안 정책 위반", "2FA 미사용", "경고"],
        ["2026-06-28", "외부 서비스 연동", "승인되지 않은 API 연동", "차단"],
    ]
    abnormal_table = create_table(abnormal_data, [80, 80, 140, 100])
    apply_table_style(abnormal_table)
    story.append(abnormal_table)
    story.append(Spacer(1, 6*mm))

    story.append(Paragraph("5.4. 보안 위험도 종합 평가", styles["SubSectionTitle"]))
    story.append(Spacer(1, 4*mm))

    risk_data = [
        ["평가 항목", "위험도", "비고"],
        ["개인정보 보호", "중간", "이메일 내 개인정보 포함 사례 있음"],
        ["접근 통제", "낮음", "대부분 정상적인 접근"],
        ["데이터 유출", "중간", "민감 문서 외부 공유 사례 있음"],
        ["계정 보안", "중간", "2FA 미사용, 계정 공유 의심"],
        ["외부 서비스", "중간", "승인되지 않은 서비스 사용 사례 있음"],
        ["종합 위험도", "중간", "관리 필요"],
    ]
    risk_table = create_table(risk_data, [100, 80, 220])
    apply_table_style(risk_table)
    story.append(risk_table)

    story.append(PageBreak())

    # ==================== 6. 종합 평가 및 제언 ====================
    story.append(SectionHeader("6. 종합 평가 및 제언", page_width))
    story.append(Spacer(1, 8*mm))

    story.append(Paragraph("6.1. 종합 평가", styles["SubSectionTitle"]))
    story.append(Spacer(1, 4*mm))

    story.append(Paragraph(
        "김민기 대리는 2026년 2분기 동안 총 2,823건의 로깅 데이터를 기록하며 "
        "안정적인 업무 활동을 보였습니다. 주요 평가 항목은 다음과 같습니다.",
        styles["BodyText10"]
    ))
    story.append(Spacer(1, 4*mm))

    eval_data = [
        ["평가 항목", "등급", "비고"],
        ["업무 집중도", "A", "13:00~17:00 시간대 높은 집중도"],
        ["협업 활동", "A", "47명과의 활발한 상호작용"],
        ["AI 도구 활용", "B", "XCureNet AI Assistant 적극 활용"],
        ["보안 준수", "C", "민감 정보 노출 가능성 존재"],
        ["외부 서비스", "B", "승인되지 않은 서비스 사용 사례 있음"],
        ["종합 평가", "B", "안정적인 업무 활동, 보안 관리 필요"],
    ]
    eval_table = create_table(eval_data, [100, 60, 240])
    apply_table_style(eval_table)
    story.append(eval_table)
    story.append(Spacer(1, 8*mm))

    story.append(Paragraph("6.2. 주요 발견 사항", styles["SubSectionTitle"]))
    story.append(Spacer(1, 4*mm))

    findings = [
        "<bullet>•</bullet> <b>업무 패턴:</b> 13:00~17:00 시간대에 가장 높은 업무 집중도를 보였으며, "
        "이는 전형적인 9시 출근 직원의 패턴과 일치합니다.",
        "<bullet>•</bullet> <b>협업 관계:</b> 기술기획팀(20.4%)과 개발팀(17.3%)과의 협업이 가장 활발했으며, "
        "프로젝트 기반의 긴밀한 협업이 이루어지고 있습니다.",
        "<bullet>•</bullet> <b>AI 도구 활용:</b> XCureNet AI Assistant를 문서 작성 및 요약에 "
        "적극 활용하고 있으며, AI 도구 사용 비중이 전체 로깅의 33.3%를 차지합니다.",
        "<bullet>•</bullet> <b>보안 이슈:</b> 개인정보 포함 이메일(8건), 비밀번호 평문 전송(3건), "
        "민감 문서 외부 공유(5건) 등 보안 관련 이슈가 확인되었습니다.",
        "<bullet>•</bullet> <b>비정상 활동:</b> 7건의 비정상 활동이 확인되었으며, "
        "대부분 차단 또는 경고 조치로 대응되었습니다.",
    ]
    for finding in findings:
        story.append(Paragraph(finding, styles["BulletText"]))
    story.append(Spacer(1, 8*mm))

    story.append(Paragraph("6.3. 제언 사항", styles["SubSectionTitle"]))
    story.append(Spacer(1, 4*mm))

    recommendations = [
        "<bullet>•</bullet> <b>보안 교육 강화:</b> 개인정보 보호 및 보안 정책 준수에 대한 "
        "정기 교육이 필요합니다. 특히 이메일 내 개인정보 포함 사례가 다수 확인되었습니다.",
        "<bullet>•</bullet> <b>2FA 의무화:</b> 2FA 미사용 사례가 확인되었으므로, "
        "모든 직원에게 2FA 적용을 의무화해야 합니다.",
        "<bullet>•</bullet> <b>외부 서비스 관리:</b> 승인되지 않은 외부 서비스 사용 사례가 "
        "확인되었으므로, 외부 서비스 사용 가이드라인을 강화해야 합니다.",
        "<bullet>•</bullet> <b>업무 패턴 분석:</b> 13:00~17:00 시간대의 높은 집중도를 "
        "활용하여 중요한 업무는 이 시간대에 배치하는 것이 효율적입니다.",
        "<bullet>•</bullet> <b>AI 도구 활용 확대:</b> AI 도구 사용이 활발하므로, "
        "XCureNet AI Analytics와 같은 고급 도구의 활용을 확대할 것을 권장합니다.",
        "<bullet>•</bullet> <b>정기 모니터링:</b> 비정상 활동이 지속적으로 확인되고 있으므로, "
        "정기적인 모니터링 체계를 강화해야 합니다.",
    ]
    for rec in recommendations:
        story.append(Paragraph(rec, styles["BulletText"]))
    story.append(Spacer(1, 10*mm))

    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER_GRAY))
    story.append(Spacer(1, 6*mm))
    story.append(Paragraph(
        "<i>본 보고서는 XCureNet 분석팀에서 작성한 내부 문서로, 무단 배포를 금합니다.</i>",
        styles["SmallText"]
    ))
    story.append(Paragraph(
        "<i>문의: 분석팀 (analysis@xcurenet.com)</i>",
        styles["SmallText"]
    ))

    # ==================== PDF 생성 ====================
    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    print(f"보고서가 생성되었습니다: {output_path}")
    return output_path


if __name__ == "__main__":
    generate_report()
