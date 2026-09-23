def number_to_words(n):
    ones = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
            "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
            "sixteen", "seventeen", "eighteen", "nineteen"]

    tens = ["", "", "twenty", "thirty", "forty", "fifty",
            "sixty", "seventy", "eighty", "ninety"]

    if n == 0:
        return "zero"
    if n < 20:
        return ones[n]
    if n < 100:
        return tens[n // 10] + (f"-{ones[n % 10]}" if n % 10!= 0 else "")
    if n < 1000:
        # İngiliz İngilizcesi istersen: f"{ones[n // 100]} hundred and {number_to_words(n % 100)}"
        return ones[n // 100] + " hundred" + (f" {number_to_words(n % 100)}" if n % 100!= 0 else "")

# 1'den 500'e kadar yazdır
for i in range(1, 1000):
    print(number_to_words(i))

# Dosyaya kaydetmek istersen:
# with open("numbers.txt", "w", encoding="utf-8") as f:
# for i in range(1, 501):
# f.write(f"{i}: {number_to_words(i)}\n")