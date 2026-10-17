def parse_csv_record(text):
    if "\n" in text or "\r" in text:
        raise ValueError("expected one record")
    return text.split(",")
