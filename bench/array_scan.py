import sys


def main():
    n = int(sys.argv[1])
    values = []
    i = 0
    while i < n:
        value = (i * 17 + 3) % 1009
        values.append(value)
        i = i + 1

    total = 0
    hits = 0
    j = 0
    while j < len(values):
        value = values[j]
        total = total + value
        if value % 97 == 0:
            hits = hits + 1
        j = j + 1

    sys.stdout.write(str(n) + "|" + str(total) + "|" + str(hits) + "\n")


if __name__ == "__main__":
    main()
