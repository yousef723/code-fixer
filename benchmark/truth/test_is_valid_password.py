from solution import is_valid_password

def test_it():
    assert is_valid_password("Abcdefg1") is True
    assert is_valid_password("abcdefgh") is False
    assert is_valid_password("Ab1") is False
    assert is_valid_password("abcdefg1") is False
    assert is_valid_password("ABCDEFG1") is True
