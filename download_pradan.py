#!/usr/bin/env python3

import requests
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

MAX_RETRIES = 5
RETRY_WAIT_SECONDS = 30
CHUNK_SIZE_MB = 8

url_prefix = "https://pradan.issdc.gov.in"

cookie_string = "FGTServer=5DB1E9B68132028CF7976EE4DF4CBB47C2F908C978D8DADB79380837E680FA20672DD56B0798AF391BF6;JSESSIONID=00cead864c9c4117f2b0f001bc66;OAuth_Token_Request_State=098d7b21-325b-4fd1-b174-ae6704cffdaf;JSESSIONID=00cfb289f70d0b97f9e36369a0c4;FGTServer=5DB1E9B68132028CF7976EE4DF4CBB47C2F908C978D8DADB79380837E680FA20672DD56B0798AF381BF6;" 

headers = {
"Cookie": cookie_string
}

data_file_paths = ["/ch2/protected/downloadData/POST_OD/isda_archive/ch2_bundle/cho_bundle/nop/ohr_collection/data/calibrated/20260103/ch2_ohr_ncp_20260103T1005176450_d_img_d18.zip?ohrc", "/ch2/protected/downloadData/POST_OD/isda_archive/ch2_bundle/cho_bundle/nop/ohr_collection/data/calibrated/20260103/ch2_ohr_ncp_20260103T0609041371_d_img_d18.zip?ohrc", "/ch2/protected/downloadData/POST_OD/isda_archive/ch2_bundle/cho_bundle/nop/ohr_collection/data/calibrated/20260103/ch2_ohr_ncp_20260103T1203563771_d_img_d18.zip?ohrc", "/ch2/protected/downloadData/POST_OD/isda_archive/ch2_bundle/cho_bundle/nop/ohr_collection/data/calibrated/20260103/ch2_ohr_ncp_20260103T0410224157_d_img_d18.zip?ohrc", "/ch2/protected/downloadData/POST_OD/isda_archive/ch2_bundle/cho_bundle/nop/ohr_collection/data/calibrated/20260102/ch2_ohr_ncp_20260102T1819015920_d_img_d18.zip?ohrc", "/ch2/protected/downloadData/POST_OD/isda_archive/ch2_bundle/cho_bundle/nop/ohr_collection/data/calibrated/20260102/ch2_ohr_ncp_20260102T2017444613_d_img_d18.zip?ohrc", "/ch2/protected/downloadData/POST_OD/isda_archive/ch2_bundle/cho_bundle/nop/ohr_collection/data/calibrated/20260102/ch2_ohr_ncp_20260102T1224107393_d_img_d18.zip?ohrc", "/ch2/protected/downloadData/POST_OD/isda_archive/ch2_bundle/cho_bundle/nop/ohr_collection/data/calibrated/20260102/ch2_ohr_ncp_20260102T1422564520_d_img_d18.zip?ohrc", "/ch2/protected/downloadData/POST_OD/isda_archive/ch2_bundle/cho_bundle/nop/ohr_collection/data/calibrated/20260130/ch2_ohr_ncp_20260130T1309574436_d_img_d18.zip?ohrc", "/ch2/protected/downloadData/POST_OD/isda_archive/ch2_bundle/cho_bundle/nop/ohr_collection/data/calibrated/20260130/ch2_ohr_ncp_20260130T1708191265_d_img_d18.zip?ohrc", ] 

host_name = urlparse(url_prefix).netloc
base_dir = Path.cwd()
session = requests.Session()

def keep_alive():
    keep_alive_url = url_prefix + "/ch2/protected/payload.xhtml"
    for _ in range(144):  # 24 hours
        time.sleep(600)  # 10 minutes
        try:
            session.get(keep_alive_url, headers=headers, timeout=(30, 60))
        except Exception as e:
            pass

threading.Thread(target=keep_alive, daemon=True).start()

download_count = 0
for file_index, file_path in enumerate(data_file_paths, start=1):
    url = url_prefix + file_path
    clean_path = file_path.split("?")[0]
    relative_path = clean_path.lstrip("/")
    final_file = base_dir / host_name / relative_path
    partial_file = Path(str(final_file) + ".part")
    final_file.parent.mkdir(parents=True, exist_ok=True)

    if final_file.exists():
        download_count += 1
        continue

    success = False
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resume_from = 0
            request_headers = headers.copy()
            if partial_file.exists():
                resume_from = partial_file.stat().st_size
                request_headers["Range"] = f"bytes={resume_from}-"

            with session.get(url, headers=request_headers, stream=True, timeout=(30, 600), allow_redirects=False) as response:
                if response.status_code not in (200, 206):
                    raise RuntimeError(f"HTTP {response.status_code}")
                mode = "ab" if resume_from > 0 else "wb"
                downloaded = resume_from
                with open(partial_file, mode) as f:
                    for chunk in response.iter_content(chunk_size=CHUNK_SIZE_MB * 1024 * 1024):
                        if not chunk: continue
                        f.write(chunk)
                        downloaded += len(chunk)
            partial_file.rename(final_file)
            download_count += 1
            success = True
            break
        except Exception as e:
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_WAIT_SECONDS)

    if not success:
        print(f"Error downloading {clean_path}")

print("Done downloading")
