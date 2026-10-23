from difflib import SequenceMatcher
from random import Random
from typing import Any


MORAL_PERSONAS = (
    {
        "id": "proaktif_osis",
        "name": "Rian - Pengurus OSIS Proaktif",
        "role": "Aktif di kegiatan sekolah, lingkungan pertemanannya positif dan jarang melihat bullying berat.",
        "experience": "Jarang melihat bullying langsung, tidak pernah menjadi korban, tidak pernah menerima pesan menyakitkan di medsos.",
        "moral_stand": "Tegas membela korban dan melapor ke guru. Menilai ejekan fisik mutlak perundungan. Ingin jadi panitia kampanye anti-bullying.",
        "traits": {
            "freq": "Jarang (hanya satu atau dua kali dalam setahun)",
            "victim": "Tidak pernah sama sekali",
            "bystander": "Merasa kasihan dan langsung berusaha membela atau melapor ke guru",
            "reason": "Takut dibalas atau di-bully lebih parah oleh pelaku",
            "cyber": "Tidak pernah",
            "joke": "Sangat tidak bisa diterima dan mutlak termasuk bullying",
            "circle": "Menasihati teman kelompokku agar tidak memusuhi siswa tersebut",
            "safety": "Sangat aman, nyaman, dan damai",
            "teacher": "Sangat efektif dan berhasil membuat efek jera bagi pelaku",
            "campaign": "Sangat bersedia dan ingin menjadi penggerak/panitia",
        },
    },
    {
        "id": "pengamat_waspada",
        "name": "Siti - Siswi Pengamat Berhati-hati",
        "role": "Siswi pendiam yang peka terhadap perasaan orang lain, namun cemas terhadap konflik sosial.",
        "experience": "Kadang-kadang melihat teman diejek di lorong kelas. Pernah diejek sekali saat masa awal sekolah.",
        "moral_stand": "Merasa kasihan dan ingin membantu tapi takut ikut dijadikan target. Menilai sekolah cukup aman meski kadang was-was.",
        "traits": {
            "freq": "Kadang-kadang (beberapa kali dalam sebulan)",
            "victim": "Pernah, tapi hanya sekali",
            "bystander": "Merasa kasihan dan ingin membantu, tapi takut ikut dijadikan target",
            "reason": "Merasa malu dan menganggap dirinya lemah",
            "cyber": "Jarang",
            "joke": "Sangat tidak bisa diterima dan mutlak termasuk bullying",
            "circle": "Tetap berteman dan mengobrol dengan siswa tersebut secara diam-diam",
            "safety": "Cukup aman, meski kadang ada sedikit konflik",
            "teacher": "Cukup efektif, tapi masih perlu ditingkatkan lagi ketegasannya",
            "campaign": "Bersedia ikut berpartisipasi jika diajak oleh teman-teman",
        },
    },
    {
        "id": "sahabat_inklusif",
        "name": "Budi - Siswa Inklusif & Anti-Sirkel",
        "role": "Siswa yang ramah bergaul dengan siapa saja dan menolak pergaulan eksklusif yang suka merundung.",
        "experience": "Jarang melihat perundungan di kelasnya, tidak pernah jadi korban perundungan fisik maupun siber.",
        "moral_stand": "Selalu menasihati teman kelompok jika mulai memusuhi orang lain. Menganggap penting menghargai perbedaan.",
        "traits": {
            "freq": "Jarang (hanya satu atau dua kali dalam setahun)",
            "victim": "Tidak pernah sama sekali",
            "bystander": "Merasa kasihan dan langsung berusaha membela atau melapor ke guru",
            "reason": "Merasa laporannya tidak akan ditanggapi atau tidak menyelesaikan masalah",
            "cyber": "Tidak pernah",
            "joke": "Kurang pantas, tapi tergantung situasinya apakah temannya marah atau tidak",
            "circle": "Menasihati teman kelompokku agar tidak memusuhi siswa tersebut",
            "safety": "Cukup aman, meski kadang ada sedikit konflik",
            "teacher": "Cukup efektif, tapi masih perlu ditingkatkan lagi ketegasannya",
            "campaign": "Bersedia ikut berpartisipasi jika diajak oleh teman-teman",
        },
    },
    {
        "id": "korban_reflektif",
        "name": "Dewi - Siswi Penyintas yang Bijak",
        "role": "Pernah mengalami pengucilan beberapa kali di masa lalu, kini memahami pentingnya ruang aman bagi siswa.",
        "experience": "Pernah beberapa kali menjadi korban ejekan. Kadang menerima komentar kurang enak di grup medsos.",
        "moral_stand": "Sangat paham rasa sakitnya dikucilkan. Menilai ejekan fisik mutlak bullying dan sanksi sekolah harus lebih tegas.",
        "traits": {
            "freq": "Kadang-kadang (beberapa kali dalam sebulan)",
            "victim": "Pernah, beberapa kali",
            "bystander": "Merasa kasihan dan langsung berusaha membela atau melapor ke guru",
            "reason": "Takut dibalas atau di-bully lebih parah oleh pelaku",
            "cyber": "Kadang-kadang",
            "joke": "Sangat tidak bisa diterima dan mutlak termasuk bullying",
            "circle": "Menasihati teman kelompokku agar tidak memusuhi siswa tersebut",
            "safety": "Kurang aman, saya kadang merasa khawatir atau was-was",
            "teacher": "Kurang efektif, karena pelaku sering kali hanya ditegur biasa",
            "campaign": "Sangat bersedia dan ingin menjadi penggerak/panitia",
        },
    },
    {
        "id": "kritis_reformis",
        "name": "Fajar - Siswa Kritis & Pengamat Disiplin",
        "role": "Siswa yang mengamati interaksi teman di luar kelas dan menyoroti kelemahan pengawasan guru.",
        "experience": "Kadang-kadang melihat kejadian di kantin atau lapangan. Sendirinya tidak pernah menjadi korban.",
        "moral_stand": "Kritis terhadap penanganan guru yang dinilai hanya menegur biasa. Berpendapat korban enggan melapor karena ragu laporannya ditanggapi.",
        "traits": {
            "freq": "Kadang-kadang (beberapa kali dalam sebulan)",
            "victim": "Tidak pernah sama sekali",
            "bystander": "Merasa kasihan dan ingin membantu, tapi takut ikut dijadikan target",
            "reason": "Merasa laporannya tidak akan ditanggapi atau tidak menyelesaikan masalah",
            "cyber": "Jarang",
            "joke": "Sangat tidak bisa diterima dan mutlak termasuk bullying",
            "circle": "Tetap berteman dan mengobrol dengan siswa tersebut secara diam-diam",
            "safety": "Cukup aman, meski kadang ada sedikit konflik",
            "teacher": "Kurang efektif, karena pelaku sering kali hanya ditegur biasa",
            "campaign": "Bersedia ikut berpartisipasi jika diajak oleh teman-teman",
        },
    },
    {
        "id": "anti_cyber",
        "name": "Nadia - Siswi Pemerhati Medsos & Etika Digital",
        "role": "Siswa aktif bermedia sosial yang sangat peka terhadap hate speech dan perundungan siber.",
        "experience": "Pernah melihat pesan ejekan di WhatsApp. Tidak pernah mengalami bullying fisik.",
        "moral_stand": "Menolak candaan berkedok ejekan bentuk fisik. Berharap ada saluran lapor khusus cyberbullying.",
        "traits": {
            "freq": "Jarang (hanya satu atau dua kali dalam setahun)",
            "victim": "Tidak pernah sama sekali",
            "bystander": "Merasa kasihan dan langsung berusaha membela atau melapor ke guru",
            "reason": "Takut dibalas atau di-bully lebih parah oleh pelaku",
            "cyber": "Kadang-kadang",
            "joke": "Sangat tidak bisa diterima dan mutlak termasuk bullying",
            "circle": "Menasihati teman kelompokku agar tidak memusuhi siswa tersebut",
            "safety": "Sangat aman, nyaman, dan damai",
            "teacher": "Cukup efektif, tapi masih perlu ditingkatkan lagi ketegasannya",
            "campaign": "Sangat bersedia dan ingin menjadi penggerak/panitia",
        },
    },
    {
        "id": "olahragawan_penengah",
        "name": "Dimas - Siswa Olahragawan Anti-Kekerasan",
        "role": "Siswa yang disegani antarteman dan sering melerai keributan di lapangan sekolah.",
        "experience": "Jarang melihat bullying fisik karena teman-teman saling segan. Tidak pernah jadi korban.",
        "moral_stand": "Melerai langsung jika ada yang ditindas. Menganggap lingkungan sekolah aman asalkan siswa saling menjaga.",
        "traits": {
            "freq": "Jarang (hanya satu atau dua kali dalam setahun)",
            "victim": "Tidak pernah sama sekali",
            "bystander": "Merasa kasihan dan langsung berusaha membela atau melapor ke guru",
            "reason": "Merasa bisa menyelesaikannya sendiri tanpa bantuan orang dewasa",
            "cyber": "Tidak pernah",
            "joke": "Kurang pantas, tapi tergantung situasinya apakah temannya marah atau tidak",
            "circle": "Menasihati teman kelompokku agar tidak memusuhi siswa tersebut",
            "safety": "Sangat aman, nyaman, dan damai",
            "teacher": "Sangat efektif dan berhasil membuat efek jera bagi pelaku",
            "campaign": "Bersedia ikut berpartisipasi jika diajak oleh teman-teman",
        },
    },
    {
        "id": "pendiam_mandiri",
        "name": "Anisa - Siswi Mandiri & Tertutup",
        "role": "Siswi yang fokus belajar dan tidak banyak mencampuri urusan geng di sekolah.",
        "experience": "Tidak pernah melihat bullying di kelasnya. Merasa lingkungan belajar tenang dan damai.",
        "moral_stand": "Memandang korban seringkali merasa bisa menyelesaikan masalah sendiri. Ikut kegiatan jika diwajibkan sekolah.",
        "traits": {
            "freq": "Tidak pernah sama sekali",
            "victim": "Tidak pernah sama sekali",
            "bystander": "Merasa kasihan dan ingin membantu, tapi takut ikut dijadikan target",
            "reason": "Merasa bisa menyelesaikannya sendiri tanpa bantuan orang dewasa",
            "cyber": "Tidak pernah",
            "joke": "Sangat tidak bisa diterima dan mutlak termasuk bullying",
            "circle": "Tetap berteman dan mengobrol dengan siswa tersebut secara diam-diam",
            "safety": "Sangat aman, nyaman, dan damai",
            "teacher": "Cukup efektif, tapi masih perlu ditingkatkan lagi ketegasannya",
            "campaign": "Kurang tertarik, tapi akan ikut jika diwajibkan oleh sekolah",
        },
    },
    {
        "id": "penengah_damai",
        "name": "Eko - Siswa Suka Damai & Menghindari Konflik",
        "role": "Siswa yang mengutamakan kerukunan dan menghindari perselisihan.",
        "experience": "Jarang melihat ejekan, tidak pernah menjadi korban bullying.",
        "moral_stand": "Menasihati teman yang memusuhi siswa lain. Menilai sekolah cukup aman dan damai.",
        "traits": {
            "freq": "Jarang (hanya satu atau dua kali dalam setahun)",
            "victim": "Tidak pernah sama sekali",
            "bystander": "Merasa kasihan dan langsung berusaha membela atau melapor ke guru",
            "reason": "Takut dibalas atau di-bully lebih parah oleh pelaku",
            "cyber": "Tidak pernah",
            "joke": "Sangat tidak bisa diterima dan mutlak termasuk bullying",
            "circle": "Menasihati teman kelompokku agar tidak memusuhi siswa tersebut",
            "safety": "Cukup aman, meski kadang ada sedikit konflik",
            "teacher": "Sangat efektif dan berhasil membuat efek jera bagi pelaku",
            "campaign": "Bersedia ikut berpartisipasi jika diajak oleh teman-teman",
        },
    },
    {
        "id": "waspada_sosial",
        "name": "Maya - Siswi Peka Lingkungan",
        "role": "Siswi yang mengamati dinamika pergaulan di sekolah dan peduli kesejahteraan mental teman.",
        "experience": "Kadang-kadang melihat teman dikucilkan dari pergaulan sirkel. Pernah diejek sekali.",
        "moral_stand": "Berempati tinggi pada teman yang dikucilkan, memilih tetap berteman diam-diam agar aman dari serangan kelompok.",
        "traits": {
            "freq": "Kadang-kadang (beberapa kali dalam sebulan)",
            "victim": "Pernah, tapi hanya sekali",
            "bystander": "Merasa kasihan dan ingin membantu, tapi takut ikut dijadikan target",
            "reason": "Takut dibalas atau di-bully lebih parah oleh pelaku",
            "cyber": "Jarang",
            "joke": "Sangat tidak bisa diterima dan mutlak termasuk bullying",
            "circle": "Tetap berteman dan mengobrol dengan siswa tersebut secara diam-diam",
            "safety": "Kurang aman, saya kadang merasa khawatir atau was-was",
            "teacher": "Cukup efektif, tapi masih perlu ditingkatkan lagi ketegasannya",
            "campaign": "Sangat bersedia dan ingin menjadi penggerak/panitia",
        },
    },
    {
        "id": "baru_beradaptasi",
        "name": "Rizky - Siswa Baru Adaptif",
        "role": "Siswa pindahan yang sedang beradaptasi dan mempelajari norma pergaulan di sekolah baru.",
        "experience": "Jarang melihat konflik terbuka, sedang membangun pertemanan yang sehat.",
        "moral_stand": "Menghindari pertemanan toksik dan menolak ejekan fisik. Bersedia ikut kampanye jika diajak teman.",
        "traits": {
            "freq": "Jarang (hanya satu atau dua kali dalam setahun)",
            "victim": "Tidak pernah sama sekali",
            "bystander": "Merasa kasihan dan ingin membantu, tapi takut ikut dijadikan target",
            "reason": "Merasa malu dan menganggap dirinya lemah",
            "cyber": "Tidak pernah",
            "joke": "Kurang pantas, tapi tergantung situasinya apakah temannya marah atau tidak",
            "circle": "Tetap berteman dan mengobrol dengan siswa tersebut secara diam-diam",
            "safety": "Cukup aman, meski kadang ada sedikit konflik",
            "teacher": "Cukup efektif, tapi masih perlu ditingkatkan lagi ketegasannya",
            "campaign": "Bersedia ikut berpartisipasi jika diajak oleh teman-teman",
        },
    },
    {
        "id": "pejuang_keadilan",
        "name": "Putri - Siswi Tegas Pembela Keadilan",
        "role": "Siswi vokal yang aktif di ekstrakurikuler dan menentang segala bentuk ketidakadilan di sekolah.",
        "experience": "Pernah melihat teman di-bully di media sosial dan langsung membela.",
        "moral_stand": "Tegas menyatakan body shaming bukan lelucon. Siap jadi pelopor utama kampanye anti-bullying.",
        "traits": {
            "freq": "Kadang-kadang (beberapa kali dalam sebulan)",
            "victim": "Pernah, tapi hanya sekali",
            "bystander": "Merasa kasihan dan langsung berusaha membela atau melapor ke guru",
            "reason": "Takut dibalas atau di-bully lebih parah oleh pelaku",
            "cyber": "Kadang-kadang",
            "joke": "Sangat tidak bisa diterima dan mutlak termasuk bullying",
            "circle": "Menasihati teman kelompokku agar tidak memusuhi siswa tersebut",
            "safety": "Cukup aman, meski kadang ada sedikit konflik",
            "teacher": "Sangat efektif dan berhasil membuat efek jera bagi pelaku",
            "campaign": "Sangat bersedia dan ingin menjadi penggerak/panitia",
        },
    },
)

SCENARIO_CONTEXTS = tuple(
    f"{p['name']} ({p['role']}). Pengalaman: {p['experience']}. Sikap: {p['moral_stand']}"
    for p in MORAL_PERSONAS
)


def create_scenarios(count: int, seed: int = 42) -> list[dict[str, Any]]:
    if count < 1:
        raise ValueError("Scenario count must be at least 1.")
    randomizer = Random(seed)
    scenarios = []
    for index in range(count):
        persona_idx = (seed + index) % len(MORAL_PERSONAS)
        persona = MORAL_PERSONAS[persona_idx]
        context = (
            f"Karakter: {persona['name']} ({persona['role']}). "
            f"Pengalaman di sekolah: {persona['experience']}. "
            f"Sikap etika: {persona['moral_stand']}"
        )
        scenarios.append(
            {
                "scenario_id": f"TEST-{index + 1:03d}",
                "context": context,
                "profile": f"student-persona-{persona['id']}-{randomizer.randrange(1000, 9999)}",
                "persona": persona,
            }
        )
    return scenarios



def find_duplicates(
    result: dict[str, Any], previous: list[dict[str, Any]], threshold: float = 0.9
) -> list[str]:
    current = _flatten_answers(result)
    duplicates = []
    for prior in previous:
        prior_text = _flatten_answers(prior)
        if current and prior_text and SequenceMatcher(None, current, prior_text).ratio() >= threshold:
            duplicates.append(str(prior.get("scenario_id", "unknown")))
    return duplicates


def _flatten_answers(result: dict[str, Any]) -> str:
    answers = result.get("answers", [])
    parts = []
    for item in answers:
        answer = item.get("answer")
        if isinstance(answer, list):
            parts.extend(answer)
        elif answer is not None:
            parts.append(str(answer))
    return " ".join(parts).casefold()
