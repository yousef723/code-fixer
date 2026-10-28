def flatten(items):
    result = []
    for item in items:
        if isinstance(item, list):
            result.append(item)
        else:
            result.append(item)
    return result
