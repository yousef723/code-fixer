from solution import second_largest

def test_it():
    assert second_largest([1, 5, 3]) == 3
    assert second_largest([4, 4, 2]) == 2
    assert second_largest([10, 9]) == 9
