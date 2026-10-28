from solution import fizzbuzz

def test_it():
    assert fizzbuzz(5) == ["1", "2", "Fizz", "4", "Buzz"]
    assert fizzbuzz(15)[-1] == "FizzBuzz"
    assert fizzbuzz(30)[29] == "FizzBuzz"
    assert fizzbuzz(0) == []
