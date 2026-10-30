from clear_context.services.report_text import claim_language, report_text


def test_turkish_letters_choose_turkish_and_everything_else_english():
    assert claim_language("Safranbolu adını safrandan alır.") == "tr"
    assert claim_language("The bridge opened in 2019.") == "en"
    # A Turkish claim without Turkish-specific letters falls back to English.
    assert claim_language("Safranbolu 1994 yilinda listeye alindi.") == "en"


def test_messages_are_formatted_in_the_chosen_language():
    assert report_text("assessment_failed", "Köprü açıldı.", status="timeout") == (
        "Kanıt değerlendirmesi tamamlanmadı (timeout); bu detay değerlendirilmedi."
    )
    assert report_text("no_evidence", "The bridge opened.").startswith("No source passage")
