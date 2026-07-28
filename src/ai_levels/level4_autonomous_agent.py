"""
🚀 CẤP ĐỘ 4: AUTONOMOUS AGENT (Agent tự chủ với Planning & Memory)
Tự chia nhỏ mục tiêu, dùng kết quả bước trước cho bước sau và lưu memory.
"""

from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from tools import check_slots, list_doctors, suggest_specialty  # noqa: E402


class AutonomousGoalAgent:
    def __init__(self, goal: str, max_steps: int = 4):
        self.goal = goal
        self.max_steps = max_steps
        self.memory = []
        date_match = re.search(r"\b\d{4}-\d{2}-\d{2}\b", goal)
        self.appointment_date = (
            date_match.group(0) if date_match else "2026-08-01"
        )

    def create_plan(self):
        """Decompose the goal before execution; later steps depend on memory."""
        return [
            "Định tuyến chuyên khoa từ triệu chứng",
            "Dùng chuyên khoa trong memory để tìm bác sĩ có lịch",
            "Dùng bác sĩ trong memory để kiểm tra slot",
        ][: self.max_steps]

    @staticmethod
    def _specialty_from_memory(memory):
        if not memory:
            return ""
        match = re.search(
            r"Gợi ý chuyên khoa:\s*([^\n]+)",
            memory[-1]["result"],
        )
        return match.group(1).strip() if match else ""

    @staticmethod
    def _doctor_from_memory(memory):
        if not memory:
            return ""
        match = re.search(
            r"^\d+\.\s+(BS\..+)$",
            memory[-1]["result"],
            re.MULTILINE,
        )
        return match.group(1).strip() if match else ""

    def execute(self):
        print(f"🚀 === Bắt đầu Autonomous Goal: {self.goal} ===")

        plan = self.create_plan()
        print(f"📋 [Plan Created]: {len(plan)} mục tiêu con.")

        for step, objective in enumerate(plan, start=1):
            print(f"\n--- Planning & Action (Step {step}/{len(plan)}) ---")

            if step == 1:
                action = "suggest_specialty(goal)"
                result = suggest_specialty(self.goal)
            elif step == 2:
                specialty = self._specialty_from_memory(self.memory)
                if not specialty:
                    print("🛑 Không đủ dữ liệu để tiếp tục plan.")
                    break
                action = (
                    f"list_doctors({specialty!r}, "
                    f"{self.appointment_date!r})"
                )
                result = list_doctors(specialty, self.appointment_date)
            else:
                doctor = self._doctor_from_memory(self.memory)
                if not doctor:
                    print("🛑 Không có bác sĩ trong memory để kiểm tra slot.")
                    break
                action = (
                    f"check_slots({doctor!r}, "
                    f"{self.appointment_date!r})"
                )
                result = check_slots(doctor, self.appointment_date)

            self.memory.append(
                {
                    "step": step,
                    "plan": objective,
                    "action": action,
                    "result": result,
                }
            )
            print(f"📋 [Planning]: {objective}")
            print(f"🛠️ [Execution]: {action} ➔ {result}")
            print(f"💾 [Memory Saved]: Logged step {step} to memory.")

        print(
            "🎯 [Goal Evaluation]: Đã có dữ liệu tư vấn. "
            "Chờ người dùng xác nhận giờ và tên trước khi đặt lịch."
        )


if __name__ == "__main__":
    agent = AutonomousGoalAgent(
        "Tôi hay đầy hơi và khó tiêu, hãy tìm lịch khám phù hợp."
    )
    agent.execute()
