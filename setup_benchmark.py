from pathlib import Path

cases = {
"median": r'''def median(nums):
    n = len(nums)
    mid = n // 2
    if n % 2 == 1:
        return nums[mid]
    return (nums[mid - 1] + nums[mid]) / 2
''',
"fizzbuzz": r'''def fizzbuzz(n):
    out = []
    for i in range(1, n + 1):
        if i % 3 == 0:
            out.append("Fizz")
        elif i % 5 == 0:
            out.append("Buzz")
        elif i % 15 == 0:
            out.append("FizzBuzz")
        else:
            out.append(str(i))
    return out
''',
"count_words": r'''def count_words(text):
    return len(text.split(" "))
''',
"second_largest": r'''def second_largest(nums):
    ordered = sorted(set(nums))
    return ordered[-1]
''',
"flatten": r'''def flatten(items):
    result = []
    for item in items:
        if isinstance(item, list):
            result.append(item)
        else:
            result.append(item)
    return result
''',
"add_item": r'''def add_item(item, items=[]):
    items.append(item)
    return items
''',
"word_frequency": r'''def word_frequency(text):
    freq = {}
    for word in text.split():
        freq[word] = freq.get(word, 1) + 1
    return freq
''',
"binary_search": r'''def binary_search(items, target):
    low, high = 0, len(items) - 1
    while low < high:
        mid = (low + high) // 2
        if items[mid] == target:
            return mid
        if items[mid] < target:
            low = mid + 1
        else:
            high = mid - 1
    return -1
''',
"total_script": r'''total = 0
for n in [1, 2, 3, 4]:
    total += n
print("Total:", total
''',
"is_valid_password": r'''def is_valid_password(pw):
    has_digit = any(c.isdigit() for c in pw)
    has_upper = any(c.isupper() for c in pw)
    return len(pw) >= 8 or has_digit and has_upper
''',
}

truth = {
"median": r'''from solution import median

def test_it():
    assert median([3, 1, 2]) == 2
    assert median([4, 1, 3, 2]) == 2.5
    assert median([5]) == 5
    assert median([9, 1, 5, 7, 3]) == 5
''',
"fizzbuzz": r'''from solution import fizzbuzz

def test_it():
    assert fizzbuzz(5) == ["1", "2", "Fizz", "4", "Buzz"]
    assert fizzbuzz(15)[-1] == "FizzBuzz"
    assert fizzbuzz(30)[29] == "FizzBuzz"
    assert fizzbuzz(0) == []
''',
"count_words": r'''from solution import count_words

def test_it():
    assert count_words("hello  world") == 2
    assert count_words("a b c") == 3
    assert count_words("") == 0
    assert count_words("  spaced   out  ") == 2
''',
"second_largest": r'''from solution import second_largest

def test_it():
    assert second_largest([1, 5, 3]) == 3
    assert second_largest([4, 4, 2]) == 2
    assert second_largest([10, 9]) == 9
''',
"flatten": r'''from solution import flatten

def test_it():
    assert flatten([1, [2, [3, 4]], 5]) == [1, 2, 3, 4, 5]
    assert flatten([]) == []
    assert flatten([[1], [2], [3]]) == [1, 2, 3]
''',
"add_item": r'''from solution import add_item

def test_it():
    assert add_item(1) == [1]
    assert add_item(2) == [2]
    assert add_item(3, [9]) == [9, 3]
''',
"word_frequency": r'''from solution import word_frequency

def test_it():
    assert word_frequency("a b a") == {"a": 2, "b": 1}
    assert word_frequency("") == {}
    assert word_frequency("x x x") == {"x": 3}
''',
"binary_search": r'''from solution import binary_search

def test_it():
    assert binary_search([1, 3, 5, 7], 7) == 3
    assert binary_search([1, 3, 5, 7], 1) == 0
    assert binary_search([1, 3, 5, 7], 4) == -1
    assert binary_search([5], 5) == 0
    assert binary_search([], 5) == -1
''',
"total_script": r'''import runpy

def test_it(capsys):
    runpy.run_path("solution.py")
    assert capsys.readouterr().out == "Total: 10\n"
''',
"is_valid_password": r'''from solution import is_valid_password

def test_it():
    assert is_valid_password("Abcdefg1") is True
    assert is_valid_password("abcdefgh") is False
    assert is_valid_password("Ab1") is False
    assert is_valid_password("abcdefg1") is False
    assert is_valid_password("ABCDEFG1") is True
''',
}

Path("benchmark/cases").mkdir(parents=True, exist_ok=True)
Path("benchmark/truth").mkdir(parents=True, exist_ok=True)
for name, code in cases.items():
    Path("benchmark/cases", name + ".py").write_text(code)
for name, code in truth.items():
    Path("benchmark/truth", "test_" + name + ".py").write_text(code)
print("benchmark folder created")