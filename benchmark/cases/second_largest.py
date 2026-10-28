def second_largest(nums):
    ordered = sorted(set(nums))
    return ordered[-1]
