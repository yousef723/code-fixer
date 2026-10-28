from solution import binary_search

def test_it():
    assert binary_search([1, 3, 5, 7], 7) == 3
    assert binary_search([1, 3, 5, 7], 1) == 0
    assert binary_search([1, 3, 5, 7], 4) == -1
    assert binary_search([5], 5) == 0
    assert binary_search([], 5) == -1
