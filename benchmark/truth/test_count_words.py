from solution import count_words

def test_it():
    assert count_words("hello  world") == 2
    assert count_words("a b c") == 3
    assert count_words("") == 0
    assert count_words("  spaced   out  ") == 2
