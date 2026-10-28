from solution import word_frequency

def test_it():
    assert word_frequency("a b a") == {"a": 2, "b": 1}
    assert word_frequency("") == {}
    assert word_frequency("x x x") == {"x": 3}
