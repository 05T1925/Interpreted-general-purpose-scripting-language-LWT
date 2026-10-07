import sys


def main():
    n = int(sys.argv[1])
    i = 1
    total = 0
    while i <= n:
        total = total + i
        i = i + 1
    sys.stdout.write(str(n) + "|" + str(total) + "\n")


if __name__ == "__main__":
    main()
