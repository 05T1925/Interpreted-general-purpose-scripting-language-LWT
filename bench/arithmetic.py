import sys


def main():
    n = int(sys.argv[1])
    i = 1
    total = 0
    while i <= n:
        total = total + i
        i = i + 1
    output = str(n) + "|" + str(total) + "\n"
    sys.stdout.buffer.write(output.encode("ascii"))


if __name__ == "__main__":
    main()
