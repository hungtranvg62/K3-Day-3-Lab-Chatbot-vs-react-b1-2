"""
🛠️ TOOL REGISTRY & SCHEMAS (Role 2: Tool Engineer)

This module contains all tools that the ReAct Agent can call.

Important Guardrails:
- These tools DO NOT diagnose diseases.
- These tools DO NOT prescribe medicine.
- These tools ONLY help recommend the appropriate specialty
  and assist with appointment booking.
"""

from datetime import date, datetime
from typing import Dict, List
import random

# ==========================================================
# Fake Data
# ==========================================================

SPECIALTY_KEYWORDS: Dict[str, List[str]] = {
    "Tiêu hóa": [
        "đau dạ dày",
        "đau bụng",
        "tiêu chảy",
        "ợ chua",
        "đầy hơi",
        "khó tiêu",
    ],
    "Ngoại tổng quát": [
        "đau bụng dưới bên phải",
        "viêm ruột thừa",
        "vết thương",
        "gãy xương",
        "sưng",
        "chấn thương",
    ],
    "Tai Mũi Họng": [
        "đau họng",
        "viêm họng",
        "ngạt mũi",
        "ho",
        "viêm amidan",
    ],
    "Tim mạch": [
        "tim đập nhanh",
        "cao huyết áp",
        "hồi hộp",
    ],
}


DOCTORS: Dict[str, List[str]] = {
    "Tiêu hóa": [
        "BS. Nguyễn Văn Minh (15 năm kinh nghiệm)",
        "BS. Trần Thu Hà (8 năm kinh nghiệm)",
    ],
    "Ngoại tổng quát": [
        "BS. Lê Hoàng Nam (12 năm kinh nghiệm)",
        "BS. Phạm Hải An (9 năm kinh nghiệm)",
    ],
    "Tai Mũi Họng": [
        "BS. Nguyễn Đức Long (10 năm kinh nghiệm)",
    ],
    "Tim mạch": [
        "BS. Võ Minh Quân (20 năm kinh nghiệm)",
    ],
}


AVAILABLE_SLOTS: Dict[str, Dict[str, List[str]]] = {
    "BS. Nguyễn Văn Minh (15 năm kinh nghiệm)": {
        "2026-08-01": ["08:00", "09:30", "10:30"]
    },
    "BS. Trần Thu Hà (8 năm kinh nghiệm)": {
        "2026-08-01": ["09:00", "13:30", "15:00"]
    },
    "BS. Lê Hoàng Nam (12 năm kinh nghiệm)": {
        "2026-08-01": ["08:30", "10:00"]
    },
    "BS. Phạm Hải An (9 năm kinh nghiệm)": {
        "2026-08-01": ["14:00", "16:00"]
    },
    "BS. Nguyễn Đức Long (10 năm kinh nghiệm)": {
        "2026-08-01": ["09:00", "11:00"]
    },
    "BS. Võ Minh Quân (20 năm kinh nghiệm)": {
        "2026-08-01": ["08:00", "10:00", "14:00"]
    },
}


EMERGENCY_KEYWORDS = [
    "khó thở",
    "bất tỉnh",
    "đau ngực dữ dội",
    "chảy máu nhiều",
    "co giật",
]


# Appointment state is in-memory for this deterministic lab.
LAB_TODAY = date(2026, 7, 28)
BOOKED_APPOINTMENTS: Dict[str, Dict[str, str]] = {}
_APPOINTMENT_SEQUENCE = count(100)


def _parse_appointment_date(value: str) -> Tuple[Optional[date], Optional[str]]:
    """Validate a YYYY-MM-DD appointment date and reject past dates."""
    if not isinstance(value, str) or not value.strip():
        return None, "LỖI: Ngày khám là bắt buộc và phải có dạng YYYY-MM-DD."

    try:
        parsed = datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None, "LỖI: Ngày khám không tồn tại hoặc sai định dạng YYYY-MM-DD."

    if parsed < LAB_TODAY:
        return None, "LỖI: Không thể tra cứu hoặc đặt lịch vào ngày trong quá khứ."

    return parsed, None


def _validate_time(value: str) -> Optional[str]:
    """Return an error when a time is not a valid HH:MM value."""
    if not isinstance(value, str) or not re.fullmatch(r"\d{2}:\d{2}", value.strip()):
        return "LỖI: Giờ khám là bắt buộc và phải có dạng HH:MM."

    try:
        datetime.strptime(value.strip(), "%H:%M")
    except ValueError:
        return "LỖI: Giờ khám không tồn tại."

    return None


def _validate_patient_name(value: str) -> Optional[str]:
    """Validate the minimal patient name required by the booking contract."""
    if not isinstance(value, str):
        return "LỖI: Tên bệnh nhân là bắt buộc."

    name = value.strip()
    if not 2 <= len(name) <= 100:
        return "LỖI: Tên bệnh nhân phải có từ 2 đến 100 ký tự."

    if not any(char.isalpha() for char in name):
        return "LỖI: Tên bệnh nhân phải chứa chữ cái."

    if not all(char.isalpha() or char in " .'-" for char in name):
        return "LỖI: Tên bệnh nhân chứa ký tự không hợp lệ."

    return None


# ==========================================================
# Helper: xác thực ngày khám
# ==========================================================

def _validate_date(value: str) -> str:
    """
    Kiểm tra ngày khám. Trả về chuỗi lỗi nếu không hợp lệ, chuỗi rỗng nếu OK.

    Chặn trường hợp Agent tự bịa ngày ("hôm nay", "ngày mai", "ngày_bạn_muốn"):
    tool phải báo lỗi rõ ràng để Agent quay lại hỏi người dùng, thay vì
    trả dữ liệu trông-như-hợp-lệ khiến Agent tưởng ngày đó có thật.
    """
    if not isinstance(value, str) or not value.strip():
        return "LỖI: Thiếu ngày khám. Hãy hỏi người dùng ngày cụ thể (YYYY-MM-DD)."

    try:
        parsed = datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError:
        return (
            f"LỖI: '{value}' không phải ngày hợp lệ. "
            "Ngày phải đúng định dạng YYYY-MM-DD (ví dụ 2026-08-01) và do người dùng "
            "cung cấp. Không được tự suy ra 'hôm nay' hay 'ngày mai'."
        )

    if parsed < date.today():
        return f"LỖI: Ngày {value} đã ở quá khứ. Vui lòng hỏi người dùng một ngày trong tương lai."

    return ""


# ==========================================================
# Tool 1
# ==========================================================

def suggest_specialty(symptoms: str) -> str:
    """
    Purpose: Recommend a booking specialty from a symptom description.

    Use only for routing. Do not use this result as a diagnosis or prescription.

    Args:
        symptoms: Non-empty patient symptom description.

    Returns:
        A specialty recommendation, an emergency stop message, a request for
        more detail, or a non-raising error string.

    Error semantics:
        Invalid input returns ``LỖI: ...``; no business error raises.

    Side effects:
        None (read-only).

    Example:
        ``suggest_specialty("đầy hơi và khó tiêu")`` -> ``Tiêu hóa``.

    Safety:
        Emergency keywords stop online booking. Output is routing only.
    """
    try:
        if not isinstance(symptoms, str) or not symptoms.strip():
            return "LỖI: Vui lòng cung cấp mô tả triệu chứng."

        text = symptoms.lower().strip()

        # Guardrail: emergency symptoms
        for keyword in EMERGENCY_KEYWORDS:
            if keyword in text:
                return (
                    "⚠️ Dấu hiệu có thể là tình huống khẩn cấp. "
                    "Vui lòng đến bệnh viện hoặc cơ sở cấp cứu gần nhất "
                    "hoặc gọi số cấp cứu thay vì đặt lịch trực tuyến."
                )

        # Prefer the longest matching phrase so a specific symptom such as
        # "đau bụng dưới bên phải" wins over the generic "đau bụng".
        matches = []
        for specialty, keywords in SPECIALTY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    matches.append((len(keyword), specialty))

        if matches:
            _, specialty = max(matches, key=lambda item: item[0])
            return (
                f"Gợi ý chuyên khoa: {specialty}\n"
                "Lưu ý: Đây chỉ là gợi ý đặt lịch, "
                "không phải chẩn đoán y khoa."
            )

        return (
            "Không xác định được chuyên khoa phù hợp. "
            "Vui lòng mô tả triệu chứng chi tiết hơn."
        )

    except Exception as e:
        return f"LỖI TOOL: {e}"


# ==========================================================
# Tool 2
# ==========================================================

def list_doctors(specialty: str, date: str) -> str:
    """
    Purpose: List doctors who have at least one slot for a specialty and date.

    Args:
        specialty: Exact specialty returned by ``suggest_specialty``.
        date: Future appointment date in YYYY-MM-DD format.

    Returns:
        A formatted doctor list, a no-availability message, or an error string.

    Error semantics:
        Unknown specialties and invalid/past dates return messages; no crash.

    Side effects:
        None (read-only).

    Example:
        ``list_doctors("Tiêu hóa", "2026-08-01")`` returns two doctors.

    Safety:
        A doctor is listed only when a real slot exists for the requested date.
    """
    try:
        date_error = _validate_date(date)
        if date_error:
            return date_error

        if specialty not in DOCTORS:
            return f"Không tìm thấy chuyên khoa '{specialty}'."

        doctors = [
            doctor
            for doctor in DOCTORS[specialty]
            if AVAILABLE_SLOTS.get(doctor, {}).get(date.strip())
        ]

        if not doctors:
            return (
                f"Không có bác sĩ khoa {specialty} còn lịch vào ngày "
                f"{date.strip()}."
            )

        result = (
            f"Danh sách bác sĩ khoa {specialty} "
            f"({date.strip()}):\n"
        )

        for i, doctor in enumerate(doctors, start=1):
            result += f"{i}. {doctor}\n"

        return result

    except Exception as e:
        return f"LỖI TOOL: {e}"


# ==========================================================
# Tool 3
# ==========================================================

def check_slots(doctor_name: str, date: str) -> str:
    """
    Purpose: Check current appointment slots for one doctor and date.

    Args:
        doctor_name: Exact full doctor name returned by ``list_doctors``.
        date: Future appointment date in YYYY-MM-DD format.

    Returns:
        Available slots, a full-schedule message, or an error string.

    Error semantics:
        Unknown doctors and invalid/past dates return messages; no crash.

    Side effects:
        None (read-only).

    Example:
        ``check_slots("BS. Nguyễn Văn Minh (15 năm kinh nghiệm)",
        "2026-08-01")`` returns ``08:00, 09:30, 10:30``.

    Safety:
        Returned slots are copied from current in-memory availability.
    """
    try:
        date_error = _validate_date(date)
        if date_error:
            return date_error

        doctor_schedule = AVAILABLE_SLOTS.get(doctor_name)

        if doctor_schedule is None:
            return "Không tìm thấy bác sĩ."

        slots = doctor_schedule.get(date)

        # Phân biệt rõ 2 tình huống: chưa có dữ liệu lịch cho ngày đó,
        # khác hẳn với bác sĩ có lịch nhưng đã đặt hết.
        if slots is None:
            return (
                f"Chưa có dữ liệu lịch khám của {doctor_name} cho ngày {date}. "
                "Hãy đề nghị người dùng chọn ngày khác."
            )

        if len(slots) == 0:
            return "Bác sĩ đã kín lịch vào ngày này."

        return (
            f"Lịch trống của {doctor_name} ({date}):\n"
            + ", ".join(slots)
        )

    except Exception as e:
        return f"LỖI TOOL: {e}"


# ==========================================================
# Tool 4
# ==========================================================

def book_appointment(
    doctor_name: str,
    date: str,
    time: str,
    patient_name: str,
) -> str:
    """
    Purpose: Create exactly one appointment after doctor and slot validation.

    Args:
        doctor_name: Exact selected doctor name.
        date: Future appointment date in YYYY-MM-DD format.
        time: Existing available slot in HH:MM format.
        patient_name: Patient name; no extra identity or financial data.

    Returns:
        A confirmation containing an application-generated appointment ID, or
        an error string.

    Error semantics:
        Missing/invalid fields and unavailable slots return messages; no crash.

    Side effects:
        Removes the booked slot and stores an in-memory appointment record.

    Example:
        ``book_appointment(doctor, "2026-08-01", "08:00", "Nguyễn An")``.

    Safety:
        Never books an unknown doctor/date/slot and never accepts an empty or
        instruction-like patient name.
    """
    try:
        date_error = _validate_date(date)
        if date_error:
            return date_error

        if not isinstance(patient_name, str) or not patient_name.strip():
            return "LỖI: Thiếu tên bệnh nhân. Hãy hỏi người dùng trước khi đặt lịch."

        if doctor_name not in AVAILABLE_SLOTS:
            return "Không tìm thấy bác sĩ."

        if date not in AVAILABLE_SLOTS[doctor_name]:
            return f"Chưa có dữ liệu lịch khám cho ngày {date}."

        slots = AVAILABLE_SLOTS[doctor_name][date]

        if time not in slots:
            return (
                "Khung giờ đã được đặt hoặc không tồn tại."
            )

        # Remove booked slot
        slots.remove(time)

        appointment_id = f"APT-{date.replace('-', '')}-{next(_APPOINTMENT_SEQUENCE)}"
        BOOKED_APPOINTMENTS[appointment_id] = {
            "patient_name": patient_name,
            "doctor_name": doctor_name,
            "date": date,
            "time": time,
        }

        return (
            "✅ Đặt lịch thành công!\n"
            f"Bệnh nhân: {patient_name}\n"
            f"Bác sĩ: {doctor_name}\n"
            f"Ngày: {date}\n"
            f"Giờ: {time}\n"
            f"Mã lịch hẹn: {appointment_id}"
        )

    except Exception as e:
        return f"LỖI TOOL: {e}"


# ==========================================================
# Tool Registry
# ==========================================================

AVAILABLE_TOOLS = {
    "suggest_specialty": suggest_specialty,
    "list_doctors": list_doctors,
    "check_slots": check_slots,
    "book_appointment": book_appointment,
}
