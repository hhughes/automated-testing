import sys

def twoSum(nums, target):
    seen = set()
    for i, n in enumerate(nums):
        if target - n in seen:
            return [i, nums.index(target - n)]
        else:
            seen.add(n)
    return None
