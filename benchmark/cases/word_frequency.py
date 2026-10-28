def word_frequency(text):
    freq = {}
    for word in text.split():
        freq[word] = freq.get(word, 1) + 1
    return freq
