def merge_spans(spans):
    merged = []
    for start, end in spans:
        if start > end:
            raise ValueError("span start must not exceed end")
        if merged and start < merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged
