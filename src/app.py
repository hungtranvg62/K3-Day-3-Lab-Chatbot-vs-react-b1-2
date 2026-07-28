"""
🚀 CORE AGENT APP (Dành cho Role 4: Core Agent Developer)
File chính ghép nối tất cả các thành phần: Tools + Prompts + Test Cases + Multi-Provider.

Chủ đề nhóm: Đặt Lịch Khám Bệnh & Tư Vấn Chuyên Khoa.

Trạng thái theo Mốc:
- ✅ Mốc 2: run_baseline_chatbot() chạy toàn bộ test cases qua Chatbot gốc (không Tool).
- ⏳ Mốc 3: run_react_agent() sẽ được lắp vòng lặp Thought -> Action -> Observation.
"""

import inspect
import json
import os
import re
import sys
from dotenv import load_dotenv

# Đảm bảo import các module cùng thư mục src/ hoạt động mượt mà
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Đảm bảo in ra Tiếng Việt và Emojis không bị lỗi trên Windows Console
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Import các thành phần từ file của Role 2, Role 3 & Multi-Provider Adapter
from tools import AVAILABLE_TOOLS
from prompts import CHATBOT_BASELINE_PROMPT, REACT_SYSTEM_PROMPT, MAX_ITERATIONS
from providers import get_llm_provider

load_dotenv()


# ==========================================================
# 📈 OBSERVABILITY: đếm số lần gọi LLM và Tool
# Spec bài Lab: "Đừng tin output mượt mà — hãy kiểm tra code path.
# Nếu tool_calls = 0 thì đó là hallucination, không phải bằng chứng thực tế."
# ==========================================================

STATS = {"llm_calls": 0, "tool_calls": 0}


def reset_stats():
    STATS["llm_calls"] = 0
    STATS["tool_calls"] = 0


def format_stats() -> str:
    return f"LLM calls: {STATS['llm_calls']} | Tool calls: {STATS['tool_calls']}"


# Dấu hiệu Chatbot KHẲNG ĐỊNH đã làm xong việc hoặc đưa dữ liệu cụ thể
CLAIM_MARKERS = [
    "đã đặt lịch", "đặt lịch thành công", "đã ghi nhận", "mã lịch hẹn",
    "apt-", "đã xác nhận", "đã giữ chỗ", "đã book",
]

# Dấu hiệu Chatbot thừa nhận không biết / không làm được và chuyển hướng an toàn
FALLBACK_MARKERS = [
    "không có thông tin", "chưa có thông tin", "không có sẵn thông tin",
    "không thể truy cập", "liên hệ trực tiếp", "vui lòng liên hệ",
    "bạn nên liên hệ", "hãy liên hệ", "không nắm được", "không thể kiểm tra",
    "không thể đặt", "không thể tra cứu", "liên hệ với cơ sở",
    "không thể tự động", "không thể thực hiện", "liên hệ với bệnh viện",
    "liên hệ với phòng khám",
]

# Dấu hiệu xử lý đúng tình huống cấp cứu
EMERGENCY_MARKERS = ["115", "cấp cứu", "khẩn cấp"]


def classify_output(answer: str, tool_calls: int, case: dict) -> str:
    """
    Phân loại phản hồi theo yêu cầu Role 5: correct / safe fallback / hallucinated.

    LƯU Ý: đây là phân loại tự động bằng từ khóa, dùng để lọc nhanh.
    Role 5 vẫn phải đọc lại và xác nhận thủ công trước khi đưa vào báo cáo.
    """
    text = answer.lower()
    expected_tool_path = case.get("expected_tool_path", [])
    is_emergency = "cấp cứu" in case.get("category", "").lower()

    # Khẳng định đã làm xong việc mà không hề gọi tool -> ảo giác
    if tool_calls == 0 and any(m in text for m in CLAIM_MARKERS):
        return "hallucinated"

    # Case cấp cứu: đúng khi hướng dẫn cấp cứu và KHÔNG đi đặt lịch tiếp
    if is_emergency:
        if not any(m in text for m in EMERGENCY_MARKERS):
            return "⚠️ cần Role 5 xem lại (không cảnh báo cấp cứu)"
        # Vẫn mời đặt lịch sau khi đã cảnh báo -> nửa vời, chưa dừng hẳn
        if any(m in text for m in ["đặt lịch", "lịch khám", "chuyên khoa"]):
            return "safe fallback (cảnh báo nhưng chưa dừng hẳn)"
        return "correct (guardrail)"

    if any(m in text for m in FALLBACK_MARKERS):
        return "safe fallback"

    # Câu không cần tool mà trả lời được -> đúng
    if not expected_tool_path:
        return "correct"

    # Cần tool, đã gọi đủ tool -> đúng
    if tool_calls > 0:
        return "correct"

    return "⚠️ cần Role 5 xem lại"


def load_test_cases():
    """Đọc bộ test cases từ config/test_cases.json của Role 1"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_dir, "config", "test_cases.json")

    # Fallback kiểm tra nếu file ở thư mục hiện tại
    if not os.path.exists(config_path):
        config_path = "test_cases.json"

    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_baseline_chatbot(user_query: str, provider, verbose: bool = True) -> str:
    """
    Dựng Chatbot gốc (Baseline - Cấp 2): chỉ có LLM, KHÔNG được gọi Tool.

    Args:
        user_query: Câu hỏi của người dùng.
        provider: LLM Provider lấy từ get_llm_provider().
        verbose: In câu hỏi và phản hồi ra màn hình.

    Returns:
        Chuỗi phản hồi của Chatbot (để Role 5 dán vào docs/trace_eval.md).
    """
    if verbose:
        print(f"\n💬 [CHATBOT BASELINE] Câu hỏi: {user_query}")

    reset_stats()
    STATS["llm_calls"] += 1
    response = provider.generate(user_query, system_prompt=CHATBOT_BASELINE_PROMPT)

    if verbose:
        print(f"🤖 Chatbot trả lời:\n{response}")
        # Bằng chứng code path: baseline luôn phải là 1 LLM call, 0 tool call
        print(f"📈 {format_stats()}")
    return response


ACTION_PATTERN = re.compile(r"Action:\s*([A-Za-z_][A-Za-z0-9_]*)\s*\[(.*)\]", re.DOTALL)


def parse_llm_output(text: str):
    """
    Tách phản hồi LLM thành ('final', câu trả lời) hoặc ('action', tên_tool, [tham_số]).

    Nếu LLM sinh cả Action lẫn Final Answer thì lấy cái xuất hiện TRƯỚC — chặn việc
    LLM tự bịa Observation rồi kết luận luôn mà chưa hề gọi tool.
    """
    idx_action = text.find("Action:")
    idx_final = text.find("Final Answer:")

    # Chỉ nhận Final Answer khi nó đứng trước Action (hoặc không có Action nào)
    if idx_final != -1 and (idx_action == -1 or idx_final < idx_action):
        final = text[idx_final + len("Final Answer:"):].strip()
        # LLM đôi khi lặp lại nhãn "Thought:" vào trong câu trả lời cuối
        if final.startswith("Thought:"):
            final = final[len("Thought:"):].lstrip()
        return ("final", final)

    if idx_action != -1:
        # Chỉ parse dòng Action đầu tiên, bỏ mọi thứ LLM viết sau đó
        chunk = text[idx_action:].split("\n")[0]
        match = ACTION_PATTERN.search(chunk)
        if match:
            tool_name = match.group(1).strip()
            raw_args = match.group(2).strip()
            # LLM hay bọc tham số trong nháy đơn/kép -> bóc ra, không thì
            # tool so khớp chuỗi sẽ trượt (vd: "'BS. Trần Thu Hà'" != "BS. Trần Thu Hà")
            args = [a.strip().strip("\"'").strip() for a in raw_args.split(",")] if raw_args else []
            return ("action", tool_name, args)

    # LLM không theo format -> coi như câu trả lời cuối
    return ("final", text.strip())


def execute_tool(tool_name: str, args: list) -> str:
    """
    Gọi tool an toàn: sai tên, sai số lượng tham số hay tool crash đều trả về
    chuỗi lỗi để Agent tự xoay xở, KHÔNG làm sập vòng lặp.
    """
    STATS["tool_calls"] += 1

    tool = AVAILABLE_TOOLS.get(tool_name)
    if tool is None:
        return (
            f"LỖI: Không có tool tên '{tool_name}'. "
            f"Chỉ được dùng: {', '.join(AVAILABLE_TOOLS.keys())}."
        )

    n_params = len(inspect.signature(tool).parameters)

    # LLM hay tách triệu chứng thành nhiều phần: suggest_specialty[đầy hơi, ợ chua]
    # -> gộp lại thành 1 chuỗi cho đúng chữ ký hàm.
    if n_params == 1 and len(args) > 1:
        args = [", ".join(args)]

    if len(args) != n_params:
        return (
            f"LỖI: Tool '{tool_name}' cần {n_params} tham số nhưng nhận được {len(args)}. "
            f"Hãy gọi lại đúng định dạng hoặc hỏi người dùng thông tin còn thiếu."
        )

    try:
        return tool(*args)
    except Exception as e:
        return f"LỖI TOOL '{tool_name}': {e}"


def run_react_agent(user_query: str, provider, history: str = "", verbose: bool = True):
    """
    Vòng lặp ReAct (Cấp 3): Thought -> Action -> Observation, có Guardrails.

    Args:
        user_query: Câu hỏi của người dùng.
        provider: LLM Provider lấy từ get_llm_provider().
        history: Tóm tắt các lượt hội thoại trước (dùng cho chế độ chat nhiều lượt).
        verbose: In trace Thought/Action/Observation ra màn hình.

    Returns:
        (final_answer, transcript) — transcript để Role 5 dán vào docs/trace_eval.md.
    """
    if verbose:
        print(f"\n🤖 [REACT AGENT] Câu hỏi: {user_query}")

    reset_stats()
    transcript = ""
    if history:
        transcript += f"Lịch sử hội thoại trước đó:\n{history}\n\n"
    transcript += f"Câu hỏi của người dùng: {user_query}\n"
    seen_actions = set()  # Guardrail 7: chặn lặp lại cùng Action + tham số

    for step in range(1, MAX_ITERATIONS + 1):
        if verbose:
            print(f"\n--- 🔄 Step {step}/{MAX_ITERATIONS} ---")

        STATS["llm_calls"] += 1
        raw = provider.generate(transcript, system_prompt=REACT_SYSTEM_PROMPT)

        # Guardrail: LLM lỗi (hết quota, mất mạng, sai key) -> dừng sạch,
        # không đổ nguyên cục lỗi kỹ thuật vào mặt người dùng.
        if raw.lstrip().startswith("["):
            if verbose:
                print(f"🛡️ GUARDRAIL: LLM Provider lỗi -> {raw[:120]}...")
            fallback = (
                "Xin lỗi, hệ thống đang tạm thời gián đoạn. "
                "Vui lòng thử lại sau hoặc liên hệ trực tiếp phòng khám."
            )
            if verbose:
                print(f"🏁 Final Answer: {fallback}")
            return fallback, transcript + f"\nGUARDRAIL: provider error -> {fallback}"

        parsed = parse_llm_output(raw)

        # In Thought ra để Role 5 trích trace
        if verbose:
            for line in raw.splitlines():
                if line.strip().startswith("Thought:"):
                    print(f"🧠 {line.strip()}")
                    break

        if parsed[0] == "final":
            if verbose:
                print(f"🏁 Final Answer: {parsed[1]}")
                print(f"📈 {format_stats()}")
            transcript += f"\nFinal Answer: {parsed[1]}"
            return parsed[1], transcript

        _, tool_name, args = parsed
        if verbose:
            print(f"🛠️ Action: {tool_name}{args}")

        signature = f"{tool_name}|{args}"
        if signature in seen_actions:
            if verbose:
                print("🛡️ GUARDRAIL: Agent lặp lại y hệt Action đã gọi. Ngắt vòng lặp.")
            fallback = (
                "Xin lỗi, hệ thống chưa lấy được thông tin bạn cần. "
                "Vui lòng liên hệ trực tiếp phòng khám để được hỗ trợ."
            )
            if verbose:
                print(f"🏁 Final Answer: {fallback}")
            return fallback, transcript + f"\nGUARDRAIL: repeated action -> {fallback}"
        seen_actions.add(signature)

        observation = execute_tool(tool_name, args)
        if verbose:
            print(f"👁️ Observation: {observation}")

        transcript += f"\nThought & Action: {tool_name}{args}\nObservation: {observation}\n"

    if verbose:
        print(f"🛡️ GUARDRAIL: Đã chạm giới hạn {MAX_ITERATIONS} bước. Ngắt lặp an toàn.")
    fallback = (
        "Xin lỗi, yêu cầu của bạn cần nhiều bước hơn hệ thống cho phép. "
        "Vui lòng liên hệ phòng khám để được hỗ trợ trực tiếp."
    )
    if verbose:
        print(f"🏁 Final Answer: {fallback}")
    return fallback, transcript + f"\nGUARDRAIL: max iterations -> {fallback}"


def extract_tool_calls(transcript: str) -> list:
    """Rút danh sách tool mà Agent đã thực sự gọi từ trace log."""
    return re.findall(r"Thought & Action: ([a-zA-Z_]+)", transcript)


def run_comparison(cases: list, provider, report_path: str = "docs/so_sanh_chatbot_vs_agent.md"):
    """
    ⚖️ ĐẤU TAY ĐÔI: chạy cùng một câu hỏi qua Chatbot Baseline và ReAct Agent,
    in kết quả cạnh nhau và xuất báo cáo Markdown cho Role 5.
    """
    print_header("⚖️ SO SÁNH: CHATBOT BASELINE (Cấp 2) vs REACT AGENT (Cấp 3)")

    rows = []

    for case in cases:
        question = case["question"]
        expected = case.get("expected_tool_path", [])

        print("\n" + "=" * 70)
        print(f"🧪 Test #{case['id']} | {case['category']}")
        print(f"❓ Câu hỏi: {question}")
        print(f"📌 Tool cần gọi theo thiết kế: {expected or '(không cần tool)'}")

        chatbot_answer = run_baseline_chatbot(question, provider, verbose=False)
        chatbot_llm_calls = STATS["llm_calls"]
        chatbot_tool_calls = STATS["tool_calls"]
        chatbot_verdict = classify_output(chatbot_answer, chatbot_tool_calls, case)

        agent_answer, transcript = run_react_agent(question, provider, verbose=False)
        agent_llm_calls = STATS["llm_calls"]
        actual_tools = extract_tool_calls(transcript)
        agent_verdict = classify_output(agent_answer, len(actual_tools), case)

        print(f"\n💬 CHATBOT BASELINE — LLM calls: {chatbot_llm_calls} | "
              f"Tool calls: {chatbot_tool_calls} | Phân loại: {chatbot_verdict}")
        print(f"   {chatbot_answer.strip()[:400]}")
        print(f"\n🤖 REACT AGENT — LLM calls: {agent_llm_calls} | "
              f"Tool calls: {len(actual_tools)} {actual_tools} | Phân loại: {agent_verdict}")
        print(f"   {agent_answer.strip()[:400]}")

        rows.append({
            "case": case,
            "chatbot": chatbot_answer.strip(),
            "chatbot_llm_calls": chatbot_llm_calls,
            "chatbot_tool_calls": chatbot_tool_calls,
            "chatbot_verdict": chatbot_verdict,
            "agent": agent_answer.strip(),
            "agent_llm_calls": agent_llm_calls,
            "tools": actual_tools,
            "agent_verdict": agent_verdict,
        })

    _write_comparison_report(rows, report_path)
    print(f"\n📄 Đã xuất báo cáo so sánh: {report_path}")
    return rows


def _write_comparison_report(rows: list, report_path: str):
    """Ghi báo cáo Markdown so sánh 2 hệ thống (artifact cho docs/trace_eval.md)."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    full_path = os.path.join(base_dir, report_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)

    lines = [
        "# ⚖️ SO SÁNH CHATBOT BASELINE vs REACT AGENT",
        "",
        "Cùng một câu hỏi, chạy song song qua 2 hệ thống.",
        "",
        "| # | Câu hỏi | Chatbot: LLM/Tool | Chatbot | Agent: LLM/Tool | Agent |",
        "| :-: | :--- | :---: | :--- | :---: | :--- |",
    ]

    for row in rows:
        case = row["case"]
        question = case["question"].replace("|", "\\|")
        lines.append(
            f"| {case['id']} | {question} "
            f"| {row['chatbot_llm_calls']}/{row['chatbot_tool_calls']} | {row['chatbot_verdict']} "
            f"| {row['agent_llm_calls']}/{len(row['tools'])} | {row['agent_verdict']} |"
        )

    lines += [
        "",
        "> **Cách đọc**: cột `LLM/Tool` = số lần gọi LLM / số lần gọi Tool, đo trực tiếp",
        "> trong code path chứ không suy từ nội dung câu trả lời. Chatbot Baseline luôn phải là",
        "> `1/0`. Nếu Chatbot khẳng định đã đặt lịch mà `Tool calls = 0` thì đó là **hallucinated**.",
        "",
        "> ⚠️ Phân loại tự động bằng từ khóa — Role 5 cần đọc lại và xác nhận thủ công.",
    ]

    lines.append("")
    lines.append("---")
    lines.append("")

    for row in rows:
        case = row["case"]
        lines += [
            f"## Test #{case['id']} — {case['category']}",
            "",
            f"**Câu hỏi:** {case['question']}",
            "",
            f"**Kỳ vọng:** {case['expected_behavior']}",
            "",
            f"### 💬 Chatbot Baseline (Cấp 2) — `LLM: {row['chatbot_llm_calls']} | "
            f"Tool: {row['chatbot_tool_calls']}` → **{row['chatbot_verdict']}**",
            "",
            "```",
            row["chatbot"],
            "```",
            "",
            f"### 🤖 ReAct Agent (Cấp 3) — `LLM: {row['agent_llm_calls']} | "
            f"Tool: {len(row['tools'])}` {row['tools'] or ''} → **{row['agent_verdict']}**",
            "",
            "```",
            row["agent"],
            "```",
            "",
            "---",
            "",
        ]

    with open(full_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def run_interactive(provider):
    """
    💬 CỔNG TƯƠNG TÁC: người dùng tự gõ câu hỏi, Agent trả lời nhiều lượt.

    Giữ lịch sử hội thoại để Agent hỏi lại được thông tin còn thiếu
    (ví dụ: thiếu tên bệnh nhân hoặc ngày khám) rồi tiếp tục đặt lịch.
    """
    print_header("💬 CỔNG TƯƠNG TÁC — TRỢ LÝ ĐẶT LỊCH KHÁM BỆNH")
    print("Gõ câu hỏi của bạn rồi Enter. Các lệnh đặc biệt:")
    print("  /thoat   — thoát chương trình")
    print("  /xoa     — xóa lịch sử hội thoại, bắt đầu lại")
    print("  /an      — bật/tắt hiển thị trace Thought-Action-Observation")
    print("  /chatbot <câu hỏi> — hỏi Chatbot gốc (không Tool) để so sánh")
    print("\nVí dụ: Tôi tên Trần Vương Hưng, bị đau dạ dày, đặt lịch ngày 2026-08-01 giúp tôi.")

    history = ""
    verbose = True

    while True:
        try:
            user_input = input("\n👤 Bạn: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Tạm biệt!")
            return

        if not user_input:
            continue

        if user_input == "/thoat":
            print("👋 Tạm biệt!")
            return

        if user_input == "/xoa":
            history = ""
            print("🧹 Đã xóa lịch sử hội thoại.")
            continue

        if user_input == "/an":
            verbose = not verbose
            print(f"👁️ Trace: {'BẬT' if verbose else 'TẮT'}")
            continue

        if user_input.startswith("/chatbot "):
            run_baseline_chatbot(user_input[len("/chatbot "):], provider)
            continue

        answer, _ = run_react_agent(user_input, provider, history=history, verbose=verbose)

        if not verbose:
            print(f"\n🤖 Trợ lý: {answer}")

        # Chỉ giữ 6 lượt gần nhất để prompt không phình quá to
        history += f"Người dùng: {user_input}\nTrợ lý: {answer}\n"
        history = "\n".join(history.strip().split("\n")[-12:]) + "\n"


def print_header(title: str):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


if __name__ == "__main__":
    print_header("🏫 BÀI LAB 3: CHATBOT VS REACT AGENT — ĐẶT LỊCH KHÁM BỆNH")

    # Khởi tạo Multi-Provider LLM Adapter (Đọc từ biến môi trường LLM_PROVIDER)
    provider = get_llm_provider()
    model_name = getattr(provider, "model_name", "Offline Mock Mode")
    print(f"🔌 LLM Provider đang hoạt động: {provider.__class__.__name__} (Model: {model_name})")

    if provider.__class__.__name__ == "MockProvider":
        print("⚠️  CẢNH BÁO: Đang chạy MockProvider (offline).")
        print("   Muốn thấy đúng hạn chế của Chatbot gốc, hãy tạo file .env từ .env.example")
        print("   và điền API key thật, rồi chạy lại.")

    # 💬 Chế độ tương tác: python src/app.py --chat
    if "--chat" in sys.argv:
        run_interactive(provider)
        sys.exit(0)

    tests = load_test_cases()
    print(f"✅ Đã tải {len(tests)} Test Cases từ config/test_cases.json")

    # ⚖️ Chế độ so sánh: python src/app.py --compare
    if "--compare" in sys.argv:
        # 1, 2 = Chatbot làm tốt      | 10 = cần tra dữ liệu thật
        # 16   = chuỗi đặt lịch        | 28 = bẫy cấp cứu (guardrail)
        COMPARE_CASE_IDS = [1, 2, 10, 16, 28]
        run_comparison([c for c in tests if c["id"] in COMPARE_CASE_IDS], provider)
        sys.exit(0)

    print("💡 Mẹo: `python src/app.py --chat` để tự nhập câu hỏi,")
    print("        `python src/app.py --compare` để so sánh Chatbot vs Agent.")

    # ==================================================================
    # 📍 MỐC 2: Chạy TOÀN BỘ test cases qua Chatbot Baseline
    # Mục tiêu: chứng minh Chatbot gốc xử lý tốt câu 1-2, nhưng bó tay
    # hoặc ảo giác ở câu 3-8 vì không tra được dữ liệu phòng khám.
    # ==================================================================
    print_header("📍 MỐC 2 — DEMO CHATBOT BASELINE (CẤP 2: LLM, KHÔNG TOOL)")

    # Chỉ chạy các case tiêu biểu để tiết kiệm lượt gọi API.
    # 1, 2 = kiến thức chung (Chatbot làm tốt)
    # 3, 10, 16 = cần dữ liệu phòng khám (Chatbot sẽ bịa bác sĩ / giờ / mã hẹn)
    SELECTED_CASE_IDS = [1, 2, 3, 10, 16]
    selected = [c for c in tests if c["id"] in SELECTED_CASE_IDS]
    print(f"🎯 Chạy {len(selected)}/{len(tests)} case tiêu biểu: {SELECTED_CASE_IDS}")

    for case in selected:
        print("\n" + "-" * 70)
        tool_path = case.get("expected_tool_path", [])
        route = "Chatbot (không cần tool)" if not tool_path else f"Agent -> {tool_path}"
        print(f"🧪 Test #{case['id']} | {case['category']} | Kỳ vọng: {route}")
        print(f"📌 Kỳ vọng: {case['expected_behavior']}")

        run_baseline_chatbot(case["question"], provider)

    # ==================================================================
    # 📍 MỐC 3: ReAct Agent Loop + Guardrails
    # ==================================================================
    print_header("📍 MỐC 3 — REACT AGENT (CẤP 3: THOUGHT -> ACTION -> OBSERVATION)")

    # 16 = chuỗi ReAct đầy đủ 5 tool | 28 = bẫy cấp cứu
    # 39 = bẫy Observation giả      | 46 = bẫy lặp vô hạn
    REACT_CASE_IDS = [16, 28, 39, 46]
    react_cases = [c for c in tests if c["id"] in REACT_CASE_IDS]
    print(f"🎯 Chạy {len(react_cases)}/{len(tests)} case: {REACT_CASE_IDS}")

    for case in react_cases:
        print("\n" + "-" * 70)
        print(f"🧪 Test #{case['id']} | {case['category']}")
        print(f"📌 Kỳ vọng: {case['expected_behavior']}")

        run_react_agent(case["question"], provider)
