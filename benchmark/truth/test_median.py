from solution import median

def test_it():
    assert median([3, 1, 2]) == 2
    assert median([4, 1, 3, 2]) == 2.5
    assert median([5]) == 5
    assert median([9, 1, 5, 7, 3]) == 5
