import ocr
import ai

def process_image(img_url):
    """Runs the OCR on the image."""
    text = ocr.get_text(img_url)

    print("TEXT ~~~~~~~~~~~~~~~")
    print (text)
    print("COMMENTARY ~~~~~~~~~~~~~~~")

    return ai.get_commentary(text)

def main():
    print(process_image("hhh"))

if __name__ == "__main__":
    main()