import urllib.request
import gzip
import os
import time

URL = "https://static.openfoodfacts.org/data/en.openfoodfacts.org.products.csv.gz"
DEST = "data/food_db/openfoodfacts_es.csv"

def download_and_filter():
    os.makedirs(os.path.dirname(DEST), exist_ok=True)
    print(f"[*] Starting streaming download from: {URL}")
    print(f"[*] Filtering on-the-fly and saving to: {DEST}")
    
    start_time = time.time()
    
    # Request headers to look like a browser
    req = urllib.request.Request(
        URL, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    
    try:
        response = urllib.request.urlopen(req)
        # Use gzip to decompress the stream on the fly
        gz_stream = gzip.GzipFile(fileobj=response)
        
        # Open output file
        with open(DEST, 'wb') as out_f:
            # Read first line (header)
            header_line = gz_stream.readline()
            out_f.write(header_line)
            
            headers = header_line.decode('utf-8', errors='ignore').strip().split('\t')
            
            # Find indices of interest
            try:
                idx_countries_tags = headers.index('countries_tags')
            except ValueError:
                idx_countries_tags = -1
                
            try:
                idx_countries_en = headers.index('countries_en')
            except ValueError:
                idx_countries_en = -1
                
            print(f"[i] Column index - countries_tags: {idx_countries_tags}, countries_en: {idx_countries_en}")
            
            if idx_countries_tags == -1 and idx_countries_en == -1:
                print("[-] Could not find countries column in header! Saving all rows...")
            
            count_total = 0
            count_saved = 0
            
            last_print_time = time.time()
            
            # Read line by line
            for line in gz_stream:
                count_total += 1
                
                line_lower = line.lower()
                # Fast check: openfoodfacts tags are typically en:spain or es:españa
                if b'spain' in line_lower or b'espa' in line_lower:
                    parts = line.split(b'\t')
                    is_spain = False
                    
                    if idx_countries_tags != -1 and idx_countries_tags < len(parts):
                        val = parts[idx_countries_tags].lower()
                        if b'spain' in val or b'espa' in val:
                            is_spain = True
                            
                    if not is_spain and idx_countries_en != -1 and idx_countries_en < len(parts):
                        val = parts[idx_countries_en].lower()
                        if b'spain' in val or b'espa' in val:
                            is_spain = True
                            
                    if is_spain:
                        out_f.write(line)
                        count_saved += 1
                
                # Print progress every 10 seconds or 100k lines
                current_time = time.time()
                if count_total % 100000 == 0 or current_time - last_print_time > 10:
                    print(f"    Processed {count_total:,} lines, saved {count_saved:,} Spanish products...")
                    last_print_time = current_time
            
            elapsed = time.time() - start_time
            print(f"[+] Done! Processed {count_total:,} total lines.")
            print(f"[+] Saved {count_saved:,} Spanish products in {elapsed:.1f} seconds.")
            print(f"    Output file size: {os.path.getsize(DEST) / (1024 * 1024):.2f} MB")
            
    except Exception as e:
        print(f"[-] Error: {e}")
        raise

if __name__ == "__main__":
    download_and_filter()
