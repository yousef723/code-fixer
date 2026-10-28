from solution import flatten

def test_it():
    assert flatten([1, [2, [3, 4]], 5]) == [1, 2, 3, 4, 5]
    assert flatten([]) == []
    assert flatten([[1], [2], [3]]) == [1, 2, 3]
