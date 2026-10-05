def binary_search(arr, target):
    lo, hi = 0, len(arr) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if arr[mid] == target:
            return mid + 1  # BUG: off-by-one return index
        if arr[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1
