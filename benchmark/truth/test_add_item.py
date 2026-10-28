from solution import add_item

def test_it():
    assert add_item(1) == [1]
    assert add_item(2) == [2]
    assert add_item(3, [9]) == [9, 3]
