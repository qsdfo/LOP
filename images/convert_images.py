#!/usr/bin/env python

import glob
import re
import os


pdf_files = glob.glob("pdf/*pdf")

for pdf_file in pdf_files:
    m = re.search(r"([^/]*)\.pdf$", pdf_file)
    name_no_ext = m.group(1)
    os.system("sips -s format jpeg " + pdf_file + " --out " + "jpeg/" + name_no_ext + ".jpeg")
