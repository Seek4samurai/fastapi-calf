SPARK_CHARS = "▁▂▃▄▅▆▇█"


def sparkline(values, minimum=None, maximum=None):
    if not values:
        return ""
    
    min_value = minimum if minimum is not None else min(values)
    max_value = maximum if maximum is not None else max(values)

    if max_value == min_value:
        return SPARK_CHARS[0] * len(values)

    result = []

    for value in values:
        value = max(min_value, min(value, max_value))

        normalized = (value - min_value) / (max_value - min_value)

        index = int(normalized * (len(SPARK_CHARS) - 1))

        result.append(SPARK_CHARS[index])
    
    return "".join(result)

