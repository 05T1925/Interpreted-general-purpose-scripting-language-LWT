import sys


def main():
    # S44 S11-v2 workload: same algorithm and output as dict_counts.lwt.
    # Explicit loops only (no sum/comprehension/generator shortcuts), matching
    # the other Python baselines so the language comparison stays honest.
    n = int(sys.argv[1])
    counts = {}
    i = 0
    while i < n:
        key = str((i * 17 + 3) % 1009)
        if key in counts:
            counts[key] = counts.get(key, 0) + 1
        else:
            counts[key] = 1
        i = i + 1

    output = str(n) + "|" + str(len(counts)) + "\n"
    sys.stdout.buffer.write(output.encode("ascii"))


if __name__ == "__main__":
    main()
