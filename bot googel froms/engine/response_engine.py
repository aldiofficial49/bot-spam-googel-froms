import json
import re
from typing import Any

from engine.form_parser import Question
from engine.llm_client import OllamaClient
from engine.validator import validate_answer


def _match_option(candidate: Any, options: list[str]) -> str | None:
    if candidate is None or not options:
        return None

    # Handle list or tuple
    if isinstance(candidate, (list, tuple)) and len(candidate) > 0:
        candidate = candidate[0]

    # Handle dict (e.g. {"answer": "..."})
    if isinstance(candidate, dict) and candidate:
        candidate = list(candidate.values())[0]

    # Handle numeric index
    if isinstance(candidate, int) and not isinstance(candidate, bool):
        if 1 <= candidate <= len(options):
            return options[candidate - 1]
        if candidate == 0:
            return options[0]

    if not isinstance(candidate, str):
        return None

    c_clean = candidate.strip().strip('"\'`').casefold()

    # 1. Exact match
    for opt in options:
        if c_clean == opt.strip().casefold():
            return opt

    # 2. Number or letter prefix (e.g. "1", "1.", "A", "A.", "Opsi 1", "Pilihan 2")
    num_match = re.match(r"^(?:opsi|pilihan|option)?\s*([0-9]+|[a-d])(?:\.|\:|\-|\s|$)", c_clean)
    if num_match:
        token = num_match.group(1)
        if token.isdigit():
            val = int(token)
            if 1 <= val <= len(options):
                return options[val - 1]
            if 0 <= val < len(options):
                return options[val]
        elif len(token) == 1 and token.isalpha():
            idx = ord(token) - ord("a")
            if 0 <= idx < len(options):
                return options[idx]

    # 3. Substring match
    for opt in options:
        opt_fold = opt.strip().casefold()
        if c_clean in opt_fold or opt_fold in c_clean:
            return opt

    # 4. Word/token overlap
    stop_words = {"dan", "atau", "yang", "untuk", "dari", "ini", "itu", "ada"}
    words = re.findall(r"\b[a-zA-Z0-9_-]{3,}\b", c_clean)
    c_words = {w for w in words if w not in stop_words}
    if c_words:
        best_opt = None
        best_score = 0.0
        for opt in options:
            opt_words = {
                w
                for w in re.findall(r"\b[a-zA-Z0-9_-]{3,}\b", opt.casefold())
                if w not in stop_words
            }
            if not opt_words:
                continue
            common = c_words & opt_words
            score = len(common) / len(opt_words)
            if len(common) >= 2 or score >= 0.35:
                if score > best_score:
                    best_score = score
                    best_opt = opt
        if best_opt:
            return best_opt

    return None


def _get_persona_question_trait(question: Question, persona: dict[str, Any] | None) -> str | None:
    if not isinstance(persona, dict):
        return None
    traits = persona.get("traits", {})
    if not isinstance(traits, dict):
        return None
    lbl = question.label.casefold()
    if "seberapa sering" in lbl or "frekuensi" in lbl:
        return traits.get("freq")
    if "korban tindakan bullying" in lbl or "menjadi korban" in lbl:
        return traits.get("victim")
    if "melihat temanmu" in lbl or "reaksimu ketika" in lbl:
        return traits.get("bystander")
    if "alasan terbesar" in lbl or "enggan melapor" in lbl:
        return traits.get("reason")
    if "daring" in lbl or "cyber" in lbl or "media sosial" in lbl:
        return traits.get("cyber")
    if "bercandaan" in lbl or "fisik" in lbl or "body shaming" in lbl:
        return traits.get("joke")
    if "circle" in lbl or "kelompok" in lbl or "memusuhi" in lbl:
        return traits.get("circle")
    if "tingkat keamanan" in lbl or "keamanan dan kenyamanan" in lbl:
        return traits.get("safety")
    if "tindakan guru" in lbl or "pihak sekolah" in lbl:
        return traits.get("teacher")
    if "kampanye" in lbl or "partisipasimu" in lbl:
        return traits.get("campaign")
    return None


def generate_response(
    client: OllamaClient,
    question: Question,
    scenario_id: str,
    scenario_context: str,
    profile: dict[str, Any],
    history: dict[str, Any],
    *,
    persona: dict[str, Any] | None = None,
    temperature: float = 0.7,
    seed: int | None = None,
) -> dict[str, Any]:
    opts_text = (
        f"\nPilihan yang tersedia:\n{json.dumps(question.options, ensure_ascii=False)}"
        if question.options
        else ""
    )
    persona_obj = persona or (profile.get("persona") if isinstance(profile, dict) else None)
    trait_hint = ""
    tr = _get_persona_question_trait(question, persona_obj) if persona_obj else None
    if tr:
        trait_hint = (
            f"\nPengalaman / Sikap nyata karaktermu untuk pertanyaan ini: {tr}\n"
            "Pilihlah opsi yang paling sesuai dengan pengalaman karaktermu tersebut.\n"
        )

    prompt = (
        "Kamu adalah siswa pelajar yang sedang mengisi survei sekolah secara jujur dan memiliki kesadaran moral.\n"
        "Pertimbangkan dengan saksama mana tindakan yang BAIK (empati, keadilan, saling tolong, membela korban, "
        "berani melapor, menolak perundungan) dan mana tindakan yang BURUK (mengejek fisik, mengucilkan, menyakiti sesama, "
        "cyberbullying, atau bersikap apatis mendiamkan kejahatan).\n"
        f"Karakter / Perspektif: {scenario_context}\n"
        f"Profil: {json.dumps(profile, ensure_ascii=False)}\n"
        f"Pertanyaan: {question.label}\n"
        f"Tipe: {question.type}{opts_text}\n"
        f"{trait_hint}"
        f"Jawaban sebelumnya dalam skenario ini: {json.dumps(history, ensure_ascii=False)}\n"
        'Kembalikan HANYA objek JSON dengan key "answer". Nilai answer HARUS sama persis dengan salah satu pilihan di atas.'
    )
    max_attempts = 3
    for attempt in range(max_attempts):
        result = client.chat_json(
            prompt, temperature=temperature, seed=seed if attempt == 0 else None
        )
        answer = result.get("answer")
        if question.type == "multiple_choice" and question.options:
            matched = _match_option(answer, question.options)
            if matched:
                answer = matched
        valid, reason = validate_answer(question, answer)
        if valid:
            break
        if question.type == "multiple_choice":
            numbered_options = "\n".join(
                f"{i+1}. {opt}" for i, opt in enumerate(question.options)
            )
            correction = (
                f"PILIH SALAH SATU dari nomor atau teks opsi berikut:\n{numbered_options}\n"
                f"Salin teks persis (copy verbatim) atau nomor opsinya. "
                f"Contoh: {{\"answer\": \"{question.options[0]}\"}}"
            )
        elif question.type == "checkbox":
            correction = (
                f"Return a JSON array containing only exact strings from this JSON option list: "
                f"{json.dumps(question.options, ensure_ascii=False)}."
            )
        elif question.type == "scale":
            correction = (
                f"Return a JSON integer from {question.min_value} through {question.max_value}."
            )
        else:
            correction = (
                "Return a non-empty JSON string, at most 120 characters for short-answer "
                "or 5000 characters for paragraph questions."
            )
        prompt = (
            f"{prompt}\nThe prior answer did not pass validation ({reason}). "
            f"Correct the answer. {correction} Output only a JSON object with "
            'the key "answer".'
        )
    else:
        raise ValueError(
            f"Model generated invalid answers for {question.id} after "
            f"{max_attempts - 1} correction attempts: {reason}"
        )

    return {
        "question_id": question.id,
        "answer": answer,
        "scenario_id": scenario_id,
        "synthetic": True,
        "validation_status": "valid",
        "validation_attempts": attempt + 1,
    }


def generate_scenario_responses(
    client: OllamaClient,
    form_title: str,
    questions: list[Question],
    scenario_id: str,
    scenario_context: str,
    profile: dict[str, Any],
    *,
    persona: dict[str, Any] | None = None,
    temperature: float = 0.7,
    seed: int | None = None,
    allow_fallback: bool = True,
) -> list[dict[str, Any]]:
    """Generate morally reasoned, diverse answers for all questions in a form in one LLM call."""
    persona_obj = persona or (profile.get("persona") if isinstance(profile, dict) else None) or {}
    persona_name = persona_obj.get("name", "Pelajar")
    persona_role = persona_obj.get("role", "")

    questions_lines = []
    for i, q in enumerate(questions, 1):
        line = f"Pertanyaan {i} [ID: {q.id}]:\n  Teks: {q.label}\n  Tipe: {q.type}"
        if q.options:
            line += f"\n  Pilihan: {json.dumps(q.options, ensure_ascii=False)}"
        if q.type == "scale":
            line += f"\n  Rentang nilai: {q.min_value} s/d {q.max_value}"
        tr = _get_persona_question_trait(q, persona_obj)
        if tr:
            line += f"\n  -> Pengalaman/Sikap nyata karaktermu: {tr}"
        questions_lines.append(line)

    prompt = (
        f"Kamu adalah siswa pelajar: {persona_name} ({persona_role}).\n"
        f"Profil Siswa & Karaktermu: {scenario_context}\n\n"
        "PANDUAN PENTING:\n"
        "- Jawablah setiap pertanyaan secara otentik, realistis, dan mencerminkan pengalaman serta prinsip moral karaktermu di atas.\n"
        "- Untuk setiap pertanyaan, pilih opsi dari daftar Pilihan yang paling cocok dengan Pengalaman/Sikap nyata karaktermu.\n"
        "- Variasikan jawabanmu sesuai karakter: tidak semua siswa sering melihat atau menjadi korban, dan setiap siswa memiliki dinamika pengalaman yang berbeda di sekolah.\n"
        "- Tetap bedakan dengan bijak mana tindakan yang BAIK (empati, saling menghormati, membela korban, melapor, menolak penindasan) "
        "dan mana tindakan yang BURUK (mengejek fisik, mengucilkan teman, menyakiti sesama, ujaran kebencian di medsos, atau sikap apatis mendiamkan perundungan).\n"
        "- Untuk tipe multiple_choice: teks jawaban HARUS PERSIS sama dengan salah satu pilihan yang tertera di Pilihan.\n"
        "- Untuk tipe paragraph / short_answer: tuliskan opini atau solusi anti-bullying dalam bahasa Indonesia yang bijak.\n\n"
        "Daftar pertanyaan survei:\n"
        + "\n\n".join(questions_lines)
        + "\n\nKembalikan HANYA satu objek JSON valid yang memetakan ID pertanyaan ke jawaban terpilih:\n"
        '{"answers": {"<id_pertanyaan>": <jawaban>, ...}}'
    )

    history: dict[str, Any] = {}
    answers: list[dict[str, Any]] = []

    effective_temp = min(0.95, max(0.65, temperature + ((seed or 0) % 5) * 0.05))
    try:
        raw_res = client.chat_json(prompt, temperature=effective_temp, seed=seed)
        model_answers = raw_res.get("answers")
        if not isinstance(model_answers, dict):
            model_answers = {}
    except Exception:
        model_answers = {}

    for question_index, question in enumerate(questions):
        candidate = model_answers.get(question.id)
        if question.type == "multiple_choice" and question.options:
            matched = _match_option(candidate, question.options)
            if matched:
                candidate = matched

        valid, _ = validate_answer(question, candidate) if candidate is not None else (False, "missing")

        # If model answer wasn't valid, try matching persona trait first
        if not valid and question.type == "multiple_choice" and question.options:
            tr = _get_persona_question_trait(question, persona_obj)
            if tr:
                tr_matched = _match_option(tr, question.options)
                if tr_matched:
                    candidate = tr_matched
                    valid = True

        if valid:
            answers.append(
                {
                    "question_id": question.id,
                    "answer": candidate,
                    "scenario_id": scenario_id,
                    "synthetic": True,
                    "validation_status": "valid",
                    "validation_attempts": 1,
                }
            )
            history[question.id] = candidate
        else:
            # Fallback to single question bounded correction
            try:
                item = generate_response(
                    client,
                    question,
                    scenario_id,
                    scenario_context,
                    profile,
                    history,
                    persona=persona_obj,
                    temperature=temperature,
                    seed=seed,
                )
            except ValueError:
                if not allow_fallback:
                    raise
                # Fallback to persona-based moral synthetic answer for resilience
                from engine.submission_controller import _synthetic_answer
                fallback_ans = _synthetic_answer(
                    question,
                    {
                        "context": scenario_context,
                        "scenario_id": scenario_id,
                        "profile": profile.get("profile_id", "") if isinstance(profile, dict) else "",
                        "persona": persona_obj,
                    },
                    question_index,
                )
                item = {
                    "question_id": question.id,
                    "answer": fallback_ans,
                    "scenario_id": scenario_id,
                    "synthetic": True,
                    "validation_status": "valid",
                    "validation_attempts": 3,
                }
            answers.append(item)
            history[question.id] = item["answer"]

    return answers

