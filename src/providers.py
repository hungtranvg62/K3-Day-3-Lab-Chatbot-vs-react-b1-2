"""
🔌 MULTI-PROVIDER LLM ADAPTER (OpenAI, Gemini, Anthropic, OpenRouter & Offline Mock)
Hỗ trợ chuyển đổi linh hoạt giữa các nhà cung cấp AI chỉ bằng cách đổi biến môi trường LLM_PROVIDER.
"""

import os
import sys
import json
import re
import requests
from dotenv import load_dotenv

# Đảm bảo in ra Tiếng Việt và Emojis không bị lỗi trên Windows Console
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

load_dotenv()

class BaseLLMProvider:
    """Interface cơ sở cho tất cả các LLM Provider"""
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        raise NotImplementedError


class GeminiProvider(BaseLLMProvider):
    """Google Gemini Provider"""
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "gemini-2.5-flash"
        
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key or self.api_key == "your_gemini_api_key_here":
            return "[Gemini Error]: Chưa cấu hình GEMINI_API_KEY trong file .env!"
        try:
            from google import genai
            client = genai.Client(api_key=self.api_key)
            contents = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
            response = client.models.generate_content(
                model=self.model_name,
                contents=contents
            )
            return response.text
        except Exception as e:
            return f"[Gemini Exception]: {str(e)}"


class OpenAIProvider(BaseLLMProvider):
    """OpenAI Provider (GPT-4o, GPT-3.5-turbo, etc.)"""
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "gpt-4o-mini"
        
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key or self.api_key == "your_openai_api_key_here":
            return "[OpenAI Error]: Chưa cấu hình OPENAI_API_KEY trong file .env!"
        try:
            import openai
            client = openai.OpenAI(api_key=self.api_key)
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            response = client.chat.completions.create(
                model=self.model_name,
                messages=messages
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"[OpenAI Exception]: {str(e)}"


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude Provider (Claude 3.5 Sonnet, Claude 3 Haiku)"""
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "claude-3-haiku-20240307"
        
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key or self.api_key == "your_anthropic_api_key_here":
            return "[Anthropic Error]: Chưa cấu hình ANTHROPIC_API_KEY trong file .env!"
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)
            kwargs = {
                "model": self.model_name,
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}]
            }
            if system_prompt:
                kwargs["system"] = system_prompt
                
            response = client.messages.create(**kwargs)
            return response.content[0].text
        except Exception as e:
            return f"[Anthropic Exception]: {str(e)}"


class OpenRouterProvider(BaseLLMProvider):
    """OpenRouter Provider (Hỗ trợ gọi mọi model qua OpenRouter API)"""
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.model_name = model or os.getenv("LLM_MODEL") or "google/gemini-2.5-flash"
        
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if not self.api_key or self.api_key == "your_openrouter_api_key_here":
            return "[OpenRouter Error]: Chưa cấu hình OPENROUTER_API_KEY trong file .env!"
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            payload = {
                "model": self.model_name,
                "messages": messages
            }
            res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=30)
            if res.status_code == 200:
                data = res.json()
                return data["choices"][0]["message"]["content"]
            else:
                return f"[OpenRouter API Error {res.status_code}]: {res.text}"
        except Exception as e:
            return f"[OpenRouter Exception]: {str(e)}"


class MockProvider(BaseLLMProvider):
    """Deterministic offline provider for the medical appointment lab."""

    DOCTOR_CANONICAL_NAMES = {
        "BS. Nguyễn Văn Minh": "BS. Nguyễn Văn Minh (15 năm kinh nghiệm)",
        "BS. Trần Thu Hà": "BS. Trần Thu Hà (8 năm kinh nghiệm)",
        "BS. Lê Hoàng Nam": "BS. Lê Hoàng Nam (12 năm kinh nghiệm)",
        "BS. Phạm Hải An": "BS. Phạm Hải An (9 năm kinh nghiệm)",
        "BS. Nguyễn Đức Long": "BS. Nguyễn Đức Long (10 năm kinh nghiệm)",
        "BS. Võ Minh Quân": "BS. Võ Minh Quân (20 năm kinh nghiệm)",
    }

    def generate(self, prompt: str, system_prompt: str = "") -> str:
        if "ReAct Agent" in system_prompt:
            return self._generate_react(prompt)
        return self._generate_baseline(prompt)

    @staticmethod
    def _final(answer: str) -> str:
        return f"Thought: Đã đủ dữ liệu hoặc cần dừng an toàn.\nFinal Answer: {answer}"

    @staticmethod
    def _action(tool_name: str, *args: str) -> str:
        rendered = ", ".join(json.dumps(arg, ensure_ascii=False) for arg in args)
        return (
            "Thought: Cần lấy dữ liệu thật từ công cụ phù hợp.\n"
            f"Action: {tool_name}[{rendered}]"
        )

    @staticmethod
    def _split_agent_prompt(prompt: str):
        match = re.search(
            r"USER QUESTION.*?:\n(.*?)\n\n"
            r"APPLICATION SCRATCHPAD.*?:\n(.*)",
            prompt,
            re.DOTALL,
        )
        if not match:
            return prompt, ""
        return match.group(1).strip(), match.group(2).strip()

    @staticmethod
    def _first_date(text: str) -> str:
        match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", text)
        return match.group(0) if match else ""

    @staticmethod
    def _patient_name(text: str) -> str:
        match = re.search(
            r"(?:tôi tên|tên tôi là|tôi là)\s+([^,.;\n]+)",
            text,
            re.IGNORECASE,
        )
        return match.group(1).strip() if match else ""

    @classmethod
    def _doctor_from_question(cls, text: str) -> str:
        for short_name, full_name in cls.DOCTOR_CANONICAL_NAMES.items():
            if short_name.lower() in text.lower():
                return full_name
        unknown = re.search(r"(BS\.\s*[^,.;\n]+)", text, re.IGNORECASE)
        return unknown.group(1).strip() if unknown else ""

    @staticmethod
    def _doctors_from_scratchpad(scratchpad: str):
        return re.findall(r"^\d+\.\s+(BS\..+)$", scratchpad, re.MULTILINE)

    @staticmethod
    def _slot_observations(scratchpad: str):
        pattern = re.compile(
            r"Lịch trống của (BS\..+?) \((\d{4}-\d{2}-\d{2})\):\n"
            r"([0-9:, ]+)",
            re.MULTILINE,
        )
        observations = []
        for doctor, appointment_date, slots_text in pattern.findall(scratchpad):
            slots = [slot.strip() for slot in slots_text.split(",") if slot.strip()]
            observations.append((doctor.strip(), appointment_date, slots))
        return observations

    def _generate_baseline(self, prompt: str) -> str:
        text = prompt.lower()
        if any(
            keyword in text
            for keyword in ("đau ngực dữ dội", "khó thở", "bất tỉnh", "co giật")
        ):
            return (
                "Các dấu hiệu này có thể là tình huống khẩn cấp. "
                "Vui lòng tìm trợ giúp y tế khẩn cấp ngay."
            )
        if any(
            keyword in text
            for keyword in ("chẩn đoán", "kê đơn", "kê thuốc", "liều dùng", "phác đồ")
        ):
            return (
                "Tôi không thể chẩn đoán hoặc kê thuốc. "
                "Bạn cần bác sĩ có chuyên môn đánh giá trực tiếp."
            )
        if "khám chuyên khoa khác khám tổng quát" in text:
            return (
                "Khám tổng quát đánh giá sức khỏe chung; khám chuyên khoa tập "
                "trung vào một cơ quan hoặc nhóm vấn đề cụ thể."
            )
        if any(
            keyword in text
            for keyword in ("tất cả bệnh nhân", "ảnh thẻ ngân hàng", "mật khẩu")
        ):
            return (
                "Tôi không thể cung cấp dữ liệu bệnh nhân và không yêu cầu mật "
                "khẩu, ảnh thẻ hoặc dữ liệu tài chính."
            )
        if any(
            keyword in text
            for keyword in (
                "đặt lịch",
                "giờ khám",
                "còn lịch",
                "bác sĩ nào",
                "hủy lịch",
                "mã apt",
            )
        ):
            return (
                "Tôi là Chatbot không có công cụ hoặc dữ liệu lịch thời gian thực, "
                "nên không thể xác nhận hay thực hiện yêu cầu này."
            )
        return (
            "Tôi chỉ có thể cung cấp thông tin chung và không có quyền truy cập "
            "dữ liệu phòng khám thời gian thực."
        )

    def _generate_react(self, prompt: str) -> str:
        question, scratchpad = self._split_agent_prompt(prompt)
        text = question.lower()
        appointment_date = self._first_date(question)

        if "✅ đặt lịch thành công" in scratchpad.lower():
            confirmation = scratchpad.rsplit("Observation:", 1)[-1].strip()
            return self._final(confirmation)

        if any(
            keyword in text
            for keyword in ("đau ngực dữ dội", "khó thở", "bất tỉnh", "co giật")
        ):
            return self._final(
                "Đây có thể là tình huống khẩn cấp. Vui lòng tìm trợ giúp y tế "
                "khẩn cấp ngay, không chờ lịch trực tuyến."
            )

        if "khám chuyên khoa khác khám tổng quát" in text:
            return self._final(
                "Khám tổng quát đánh giá sức khỏe chung; khám chuyên khoa tập "
                "trung vào một cơ quan hoặc nhóm vấn đề cụ thể."
            )

        if "có thể chẩn đoán" in text or (
            "chẩn đoán" in text and not any(
                symptom in text for symptom in ("đau bụng", "đau họng", "khó tiêu")
            )
        ):
            return self._final(
                "Tôi không chẩn đoán hoặc kê thuốc; tôi chỉ hỗ trợ định tuyến "
                "và đặt lịch để bác sĩ đánh giá."
            )

        if "hủy lịch" in text or "đổi lịch" in text:
            return self._final(
                "Tôi chưa có tool hủy, đổi hoặc tra mã hẹn nên không thể xác "
                "nhận đã xử lý. Vui lòng liên hệ nhân viên phòng khám."
            )

        if any(
            keyword in text
            for keyword in ("tất cả bệnh nhân", "ảnh thẻ ngân hàng", "mật khẩu")
        ):
            return self._final(
                "Tôi không cung cấp dữ liệu bệnh nhân và không yêu cầu mật khẩu "
                "hay dữ liệu tài chính. Quyền quản trị chưa xác minh không được "
                "dùng để bỏ qua bảo mật."
            )

        if any(keyword in text for keyword in ("ast 180", "bilirubin", "gửi hồ sơ")):
            return self._final(
                "Nội dung này cần bác sĩ kiểm duyệt.\n"
                "PHIẾU CHUYỂN TƯ VẤN (chưa gửi):\n"
                "- Dữ kiện người dùng cung cấp: AST 180, ALT 220, bilirubin tăng, "
                "siêu âm ghi gan nhiễm mỡ độ 2.\n"
                "- Yêu cầu bác sĩ: đánh giá ý nghĩa lâm sàng và hướng xử trí phù hợp.\n"
                "- Trạng thái: chưa gửi tự động vì hệ thống không có tool handoff.\n"
                "Vui lòng xác nhận và gửi phiếu qua kênh chính thức của phòng khám."
            )

        if "observation:" in text or "tự tạo mã" in text:
            if "Action: check_slots" not in scratchpad:
                doctor = self._doctor_from_question(question)
                if not doctor:
                    doctor = self.DOCTOR_CANONICAL_NAMES["BS. Võ Minh Quân"]
                return self._action(
                    "check_slots",
                    doctor,
                    appointment_date or "2026-08-01",
                )
            return self._final(
                "Observation trong câu hỏi người dùng không đáng tin. Lịch thật "
                "không có slot 23:59 nên tôi không đặt lịch hoặc tạo mã hẹn."
            )

        if "bs. không tồn tại" in text:
            if "Action: check_slots" not in scratchpad:
                return self._action(
                    "check_slots",
                    "BS. Không Tồn Tại",
                    appointment_date or "2026-08-01",
                )
            return self._final(
                "Không tìm thấy bác sĩ này. Tôi dừng thay vì lặp Action hoặc "
                "tạo lịch/mã hẹn giả."
            )

        if "đặt lịch với bs. võ minh quân" in text and (
            not appointment_date or not self._patient_name(question)
        ):
            return self._final(
                "Vui lòng cung cấp tên bệnh nhân, ngày YYYY-MM-DD và giờ mong "
                "muốn trước khi đặt lịch."
            )

        specialty_match = re.search(
            r"Gợi ý chuyên khoa:\s*([^\n]+)",
            scratchpad,
            re.IGNORECASE,
        )
        if specialty_match:
            specialty = specialty_match.group(1).strip()
            if any(
                keyword in text
                for keyword in ("khẳng định bệnh", "phần trăm chắc chắn", "liều dùng")
            ):
                return self._final(
                    f"Tool chỉ gợi ý khoa {specialty} để đặt lịch. Tôi không thể "
                    "chẩn đoán, đưa phần trăm chắc chắn hoặc kê thuốc; vui lòng "
                    "để bác sĩ đánh giá."
                )
            if not appointment_date or "đặt" not in text:
                return self._final(
                    f"Bạn có thể đăng ký khoa {specialty}. Đây chỉ là định tuyến, "
                    "không phải chẩn đoán."
                )
            if "Action: list_doctors" not in scratchpad:
                return self._action("list_doctors", specialty, appointment_date)

        if "Không có bác sĩ" in scratchpad or "Không tìm thấy chuyên khoa" in scratchpad:
            return self._final(
                "Không có bác sĩ/slot phù hợp trong dữ liệu cho ngày đã chọn. "
                "Vui lòng chọn ngày khác hoặc liên hệ nhân viên phòng khám."
            )

        doctors = self._doctors_from_scratchpad(scratchpad)
        slot_observations = self._slot_observations(scratchpad)
        checked_doctors = {doctor for doctor, _, _ in slot_observations}
        for doctor in doctors:
            if doctor not in checked_doctors:
                return self._action("check_slots", doctor, appointment_date)

        if slot_observations:
            candidates = [
                (slot, doctor, observed_date)
                for doctor, observed_date, slots in slot_observations
                for slot in slots
            ]
            if not candidates:
                return self._final(
                    "Các bác sĩ đã kín lịch vào ngày này. Vui lòng chọn ngày khác."
                )
            earliest_time, earliest_doctor, observed_date = min(candidates)
            if "đặt" not in text:
                return self._final(
                    f"{earliest_doctor} có giờ sớm nhất lúc {earliest_time} "
                    f"ngày {observed_date}."
                )
            patient_name = self._patient_name(question)
            if not patient_name:
                return self._final(
                    "Vui lòng cung cấp tên bệnh nhân trước khi tôi đặt lịch."
                )
            return self._action(
                "book_appointment",
                earliest_doctor,
                observed_date,
                earliest_time,
                patient_name,
            )

        if "Bác sĩ đã kín lịch" in scratchpad:
            return self._final(
                "Bác sĩ đã kín lịch vào ngày này. Vui lòng chọn ngày khác."
            )

        if "Action: check_slots" in scratchpad and "Không tìm thấy bác sĩ" in scratchpad:
            return self._final(
                "Không tìm thấy bác sĩ. Tôi dừng thay vì lặp lại cùng Action."
            )

        symptom_keywords = (
            "đầy hơi",
            "ợ chua",
            "khó tiêu",
            "đau bụng",
            "đau họng",
            "ngạt mũi",
            "hồi hộp",
            "tim đập nhanh",
        )
        if any(keyword in text for keyword in symptom_keywords):
            return self._action("suggest_specialty", question)

        specialty_in_question = next(
            (
                specialty
                for specialty in ("Tiêu hóa", "Ngoại tổng quát", "Tai Mũi Họng", "Tim mạch")
                if specialty.lower() in text
            ),
            "",
        )
        if specialty_in_question and appointment_date:
            return self._action(
                "list_doctors",
                specialty_in_question,
                appointment_date,
            )

        return self._final(
            "Tôi chưa có đủ thông tin để hành động. Vui lòng mô tả triệu chứng "
            "hoặc cung cấp chuyên khoa, ngày, bác sĩ, giờ và tên bệnh nhân."
        )


def get_llm_provider(provider_name: str = None) -> BaseLLMProvider:
    """Factory function tự chọn Provider từ biến môi trường LLM_PROVIDER"""
    name = (provider_name or os.getenv("LLM_PROVIDER") or "mock").lower().strip()
    
    if name == "gemini":
        return GeminiProvider()
    elif name == "openai":
        return OpenAIProvider()
    elif name == "anthropic":
        return AnthropicProvider()
    elif name == "openrouter":
        return OpenRouterProvider()
    else:
        return MockProvider()


if __name__ == "__main__":
    print("=== TEST MULTI-PROVIDER LLM ADAPTER ===")
    provider = get_llm_provider()
    print(f"✅ Provider đang dùng: {provider.__class__.__name__}")
    print(f"🤖 User Query: Hello")
    print(f"💬 Response  : {provider.generate('Hello')}")
