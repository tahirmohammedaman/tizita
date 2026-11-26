from tizita.tts_benchmark import fold_amharic, normalise


def test_normalise_strips_ethiopic_and_latin_punctuation():
    assert normalise("ሰላም፣  ዓለም።") == "ሰላም ዓለም"
    assert normalise("  Hello, World!… ") == "hello world"


def test_amharic_homophones_fold_but_other_letters_stay():
    assert fold_amharic("ዓለም ሠላም ሐ ፀ") == "ኣለም ሰላም ሀ ጸ"  # noqa: RUF001
    assert fold_amharic("በመኪና") == "በመኪና"
