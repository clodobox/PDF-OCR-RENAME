import os
import re
import time
import shutil
from pdfminer.high_level import extract_text
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Old OCR autocorrect
#
# def autocorrect_match(match):
#   # Remove optional space after the prefix if present
#   match = match.replace(" ", "")
#   # Special case: if the string is "P0-XX-XXXX", correct it to "PO-XX-XXXX"
#   if match.startswith('P0-'):
#       return 'PO' + match[2:]
#   if match.startswith('PQ-'):
#       return 'PO' + match[2:]
#   parts = re.match(r'([A-Z]+)(\d?)-(\d{1,2})-(\d{1,4})', match)
#
#    if parts is not None:
#        prefix = parts.group(1)
#        second_digit = parts.group(3)
#        last_digits = parts.group(4)
#
#        # If the second part has only one digit, pad it with a '0' on the left
#        if len(second_digit) == 1 and second_digit != '2':
#            second_digit = "2" + second_digit
#        # If the second part has two digits and doesn't start with '2', replace the first digit with '2'
#        elif len(second_digit) == 2 and second_digit[0] != '2':
#            second_digit = '2' + second_digit[1:]
#
#        # Ensure the last part has 4 characters
#        last_digits = last_digits.zfill(4)
#
#        corrected = f'{prefix}-{second_digit}-{last_digits}'
#        return corrected
#    else:
#        return match

def autocorrect_match(match):
    match = match.replace(" ", "")

    if match.startswith('P0-'):
        match = 'PO' + match[2:]
    elif match.startswith('PQ-'):
        match = 'PO' + match[2:]
    elif match.startswith('RNW-'):
        match = 'RNWS' + match[3:]
    elif match.startswith('5P0-'):
        match = 'SPO' + match[3:]
    elif match.startswith('56R-'):
        match = 'SGR' + match[3:]

    parts = re.match(r'([A-Z]+)[-]?(\d{1,2})[-]?(\d{1,4})', match)

    if parts is not None:
        prefix = parts.group(1)
        second_part = parts.group(2).zfill(2)
        last_part = parts.group(3).zfill(4)

        # Replace characters only in the second and last parts
        second_part = second_part.replace("O", "0").replace("I", "1").replace("S", "5").replace("B", "8").replace("Z", "2").replace("G", "6")
        last_part = last_part.replace("O", "0").replace("I", "1").replace("S", "5").replace("B", "8").replace("Z", "2").replace("G", "6")

        if prefix in ["PO", "SPO", "RNWS", "SGR", "SSR"]:
            second_part = "2" + second_part[1:]

        corrected = f"{prefix}-{second_part}-{last_part}"
        return corrected
    else:
        return match


class PDFHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return

        # Get the path of the newly added file
        path = event.src_path

        # Check if the file is a PDF
        if path.endswith('.pdf'):
            print(f'Processing file: {path}')

            # Wait for a short time before processing the file
            time.sleep(3)

            try:
                # Extract the text from the PDF file
                text = extract_text(path)

                # Find all occurrences of the patterns "PO-2X-XXXX", "SPO-2X-XXXX", and "RNWS-2X-XXXX" in the text
                # matches = re.findall(r'(?:PO|SPO|RNWS)\d?-2\d-\d{4}', text)
                matches = re.findall(r'(?:P0|PO|SPO|RNWS|SGR|SSR) ?\d?-?\d{1,2}-\d{1,4}', text, re.IGNORECASE)
                matches = [match.upper() for match in matches]


                if matches:
                    # Autocorrect the matches
                    matches = [autocorrect_match(match) for match in matches]

                    # Remove duplicates from the matches list
                    matches = list(set(matches))

                    # Sort the matches list alphabetically
                    matches.sort()

                    # Join the matches list into a single string separated by underscores
                    final_name = '_'.join(matches) + '.pdf'

                    # Limit the file name length to a certain number of characters (e.g., 150 characters)
                    # 150 total minus 4 for .pdf
                    max_length = 150 - 4
                    if len(final_name) > max_length:
                        final_name = final_name[:max_length] + '.pdf'

                    # Check if a file with the same name already exists in the OUT folder
                    if os.path.exists(os.path.join('final-output', final_name)):
                        # Get the number to add to the file name
                        num = 1
                        while os.path.exists(os.path.join('final-output', final_name[:-4] + f'({num}).pdf')):
                            num += 1

                        # Add the number to the file name between parenthesis
                        final_name = final_name[:-4] + f'({num}).pdf'

                    # Rename the file with the final name
                    os.rename(path, os.path.join(os.path.dirname(path), final_name))

                    # Move the renamed file to the OUT folder
                    shutil.move(os.path.join(os.path.dirname(path), final_name), 'final-output')

                    print(f'Processed and moved file: {final_name}')
                else:
                    # Move the file to the NONAME folder
                    shutil.move(path, os.path.join('final-output', os.path.basename(path)))
                    print(f'No pattern found, moved file to OUT folder: {path}')
            except Exception as e:
                print(f'Error processing file: {path}. Error: {e}')
            # Move the file to the ERROR folder if it still exists
            if os.path.exists(path):
                if not os.path.exists('ERROR'):
                    os.mkdir('ERROR')
                shutil.move(path, os.path.join('ERROR', os.path.basename(path)))
                print(f'Moved file with error to ERROR folder: {path}')

if __name__ == "__main__":
    # Enter the path of the folder to watch
    path = 'ocr-output'

    # Create a watchdog observer and event handler
    observer = Observer()
    event_handler = PDFHandler()

    # Schedule the event handler to watch for new file creations in the specified folder
    observer.schedule(event_handler, path=path, recursive=False)
    observer.start()

    print(f'Watching folder: {path}')
	
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    
    observer.join()
# Julien Lanza