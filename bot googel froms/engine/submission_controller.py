import time
from typing import Any

from engine.form_parser import FormDefinition
from engine.llm_client import OllamaClient, OllamaError
from engine.logger import ResultLogger
from engine.response_engine import (
    _match_option,
    generate_response,
    generate_scenario_responses,
)
from engine.variation_engine import create_scenarios, find_duplicates
from engine.validator import validate_answer


MORAL_PARAGRAPH_RESPONSES = [
    "Perlu adanya edukasi berkelanjutan tentang empati dan bahaya perundungan, serta sanksi tegas yang adil bagi pelaku agar menimbulkan efek jera.",
    "Pihak sekolah harus menyediakan kotak aduan rahasia dan layanan konseling yang ramah agar korban merasa aman untuk melapor tanpa takut diancam.",
    "Budaya saling menghargai harus ditumbuhkan di setiap kelas; jangan menormalisasi ejekan fisik atau body shaming sebagai bahan candaan.",
    "Siswa harus diajarkan untuk berani bersuara dan tidak menjadi penonton pasif. Kebaikan moral menuntut kita merangkul teman yang sedang disakiti.",
    "Perlu pembentukan duta anti-bullying dan pengawasan proaktif dari guru di tempat-tempat yang rawan terjadi perundungan antarsiswa.",
    "Penting memperkuat nilai kebersamaan dan merangkul siswa yang dikucilkan agar tercipta iklim belajar yang aman, suportif, dan inklusif.",
]

MORAL_SHORT_RESPONSES = [
    "Menumbuhkan empati dan saling menghormati",
    "Tindak tegas pelaku perundungan",
    "Sediakan saluran pengaduan rahasia",
    "Edukasi anti-bullying secara rutin",
    "Rangkul teman yang dikucilkan",
    "Hentikan cyberbullying di medsos",
]


def _synthetic_answer(question: Any, scenario: dict[str, Any], index: int) -> Any:
    persona = scenario.get("persona") if isinstance(scenario, dict) else None
    traits = persona.get("traits", {}) if isinstance(persona, dict) else {}

    if question.type == "multiple_choice":
        if not question.options:
            return None

        lbl = question.label.lower()
        target_trait = None
        if "sering kamu melihat" in lbl or "kejadian perundungan" in lbl:
            target_trait = traits.get("freq")
        elif "menjadi korban" in lbl:
            target_trait = traits.get("victim")
        elif "kamu rasakan ketika melihat" in lbl or "ketika melihat temanmu" in lbl:
            target_trait = traits.get("bystander")
        elif "alasan utama" in lbl or "tidak mau melapor" in lbl:
            target_trait = traits.get("reason")
        elif "komentar negatif" in lbl or "cyberbullying" in lbl or "media sosial" in lbl:
            target_trait = traits.get("cyber")
        elif "mengejek bentuk fisik" in lbl or "hanya bercanda" in lbl:
            target_trait = traits.get("joke")
        elif "kelompok (sirkel)" in lbl or "mengucilkan seorang siswa" in lbl:
            target_trait = traits.get("circle")
        elif "keamanan dan kenyamanan" in lbl or "ancaman perundungan" in lbl:
            target_trait = traits.get("safety")
        elif "tindakan guru" in lbl or "pihak sekolah" in lbl:
            target_trait = traits.get("teacher")
        elif "kampanye anti-bullying" in lbl or "partisipasimu" in lbl:
            target_trait = traits.get("campaign")

        if target_trait:
            matched = _match_option(target_trait, question.options)
            if matched:
                return matched

        # General variation for other options
        pseudo_salt = abs(hash(f"{scenario.get('scenario_id', '')}:{question.id}:{index}"))
        chosen_idx = (index + pseudo_salt) % len(question.options)
        return question.options[chosen_idx]

    if question.type == "checkbox":
        if not question.options:
            return []
        count = 1 if len(question.options) <= 1 else ((index % 2) + 1)
        start = (index * 2) % len(question.options)
        selected = []
        for i in range(count):
            opt = question.options[(start + i) % len(question.options)]
            if opt not in selected:
                selected.append(opt)
        return selected

    if question.type == "scale":
        minimum = question.min_value if question.min_value is not None else 1
        maximum = question.max_value if question.max_value is not None else 5
        step = index % (maximum - minimum + 1)
        return minimum + step

    if question.type == "paragraph":
        salt = abs(hash(f"{scenario.get('scenario_id', '')}:{question.id}:{index}"))
        return MORAL_PARAGRAPH_RESPONSES[salt % len(MORAL_PARAGRAPH_RESPONSES)]

    salt = abs(hash(f"{scenario.get('scenario_id', '')}:{question.id}:{index}"))
    return MORAL_SHORT_RESPONSES[salt % len(MORAL_SHORT_RESPONSES)]


class SubmissionController:
    """Orchestrate dry-run or local-only tests. No response submission exists."""

    def __init__(
        self,
        *,
        max_iterations: int,
        logger: ResultLogger,
        client: OllamaClient | None = None,
        model_name: str = "qwen2.5-coder:1.5b",
        temperature: float = 0.7,
        seed: int = 42,
    ) -> None:
        self.max_iterations = max_iterations
        self.logger = logger
        self.client = client
        self.model_name = model_name
        self.temperature = temperature
        self.seed = seed

    def run(
        self, form: FormDefinition, *, mode: str, iterations: int = 1
    ) -> list[dict[str, Any]]:
        supported_modes = {"dry-run", "local-test", "remote-fill", "remote-submit"}
        if mode not in supported_modes:
            raise ValueError(
                f"Supported modes are 'dry-run', 'local-test', 'remote-fill', and 'remote-submit'; "
                f"remote submission is disabled for mode '{mode}'."
            )
        if iterations < 1 or iterations > self.max_iterations:
            raise ValueError(f"Iterations must be between 1 and {self.max_iterations}.")
        if mode == "dry-run" and self.client is None:
            raise ValueError("Dry-run requires an available Ollama client.")

        scenarios = create_scenarios(iterations, seed=self.seed)
        results: list[dict[str, Any]] = []
        for scenario_index, scenario in enumerate(scenarios):
            started = time.monotonic()
            answers: list[dict[str, Any]] = []
            try:
                if (mode == "dry-run" or mode in {"remote-fill", "remote-submit"}) and self.client is not None:
                    profile = {
                        "profile_id": scenario["profile"],
                        "synthetic": "true",
                        "persona": scenario.get("persona"),
                    }
                    answers = generate_scenario_responses(
                        self.client,
                        form.form_title,
                        form.questions,
                        scenario["scenario_id"],
                        scenario["context"],
                        profile,
                        persona=scenario.get("persona"),
                        temperature=self.temperature,
                        seed=self.seed + scenario_index,
                        allow_fallback=(mode != "dry-run"),
                    )
                else:
                    for question_index, question in enumerate(form.questions):
                        answer = _synthetic_answer(
                            question, scenario, scenario_index * len(form.questions) + question_index
                        )
                        valid, reason = validate_answer(question, answer)
                        if not valid:
                            raise ValueError(f"Fixture answer invalid for {question.id}: {reason}")
                        item = {
                            "question_id": question.id,
                            "answer": answer,
                            "scenario_id": scenario["scenario_id"],
                            "synthetic": True,
                            "validation_status": "valid",
                        }
                        answers.append(item)

            except (OllamaError, ValueError) as exc:
                self.logger.add(
                    {
                        "scenario_id": scenario["scenario_id"],
                        "model": self.model_name,
                        "question_count": min(len(answers) + 1, len(form.questions)),
                        "valid_count": len(answers),
                        "invalid_count": int(isinstance(exc, ValueError)),
                        "browser_error": "",
                        "duration_seconds": round(time.monotonic() - started, 4),
                        "status": "failed",
                        "error": str(exc),
                        "mode": mode,
                    }
                )
                raise

            if self.client is not None and (mode == "dry-run" or mode in {"remote-fill", "remote-submit"}):
                model_label = self.model_name
            elif mode == "local-test":
                model_label = "deterministic-local-test"
            else:
                model_label = "deterministic-remote-test"

            result = {
                "scenario_id": scenario["scenario_id"],
                "context": scenario["context"],
                "model": model_label,
                "mode": mode,
                "answers": answers,
            }
            result["duplicates_of"] = find_duplicates(result, results)
            results.append(result)
            self.logger.add(
                {
                    "scenario_id": scenario["scenario_id"],
                    "model": result["model"],
                    "question_count": len(answers),
                    "valid_count": len(answers),
                    "invalid_count": 0,
                    "browser_error": "",
                    "duration_seconds": round(time.monotonic() - started, 4),
                    "status": "passed",
                    "mode": mode,
                    "answers": answers,
                }
            )
        return results
