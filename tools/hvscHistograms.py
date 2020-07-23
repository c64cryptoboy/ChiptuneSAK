# Script to make sid header histograms for all the sids in an HVSC zip file

import operator
import zipfile
import itertools

from chiptunesak.constants import project_to_absolute_path
from chiptunesak import sid

# Assumes that the file is not double zipped
HVSC_LOG = project_to_absolute_path('res/HVSC72.zip')

histograms_categories = [
    'magic_id', 'version', 'data_offset', 'load_address', 'init_address',
    'play_address', 'num_subtunes', 'start_song', 'speed', 'compute sid player', 'flag_1',
    'clock', 'sid_model', 'sid2_model', 'sid3_model', 'start_page', 'page_length',
    'sid2_address', 'sid3_address', 'sid_count', 'init_sets_irq', 'init_no_irq', 'contains_basic'
]
histograms = {category: {} for category in histograms_categories}


def update_hist(category, value):
    global histograms
    if value not in histograms[category]:
        histograms[category][value] = 0
    histograms[category][value] += 1


with zipfile.ZipFile(HVSC_LOG, 'r') as hvsc_zip:
    sid_files = [fn for fn in hvsc_zip.namelist() if fn.lower().endswith('.sid')]
    for sid_file in sid_files:
        bytes = hvsc_zip.read(sid_file)
        # print("Processing %s (%d bytes)" % (sid_file, len(bytes)))

        parsed = sid.SidFile()
        parsed.parse_binary(bytes)

        update_hist('magic_id', parsed.magic_id)
        update_hist('version', parsed.version)
        update_hist('data_offset', parsed.data_offset)
        update_hist('load_address', parsed.load_address)
        update_hist('init_address', parsed.init_address)
        update_hist('play_address', parsed.play_address)
        if parsed.is_rsid:
            if parsed.play_address == 0:
                update_hist('init_sets_irq', 'RSID')
            else:
                update_hist('init_no_irq', 'RSID')
        else:
            if parsed.play_address == 0:
                update_hist('init_sets_irq', 'PSID')
            else:
                update_hist('init_no_irq', 'PSID')
        update_hist('num_subtunes', parsed.num_subtunes)
        update_hist('start_song', parsed.start_song)
        update_hist('speed', parsed.speed)
        update_hist('compute sid player', parsed.flag_0)
        update_hist('flag_1', parsed.flag_1)
        update_hist('clock', parsed.decode_clock())
        update_hist('sid_model', parsed.decode_sid_model(parsed.sid_model))
        update_hist('sid2_model', parsed.decode_sid_model(parsed.sid2_model))
        update_hist('sid3_model', parsed.decode_sid_model(parsed.sid3_model))
        update_hist('start_page', parsed.start_page)
        update_hist('page_length', parsed.page_length)
        update_hist('sid2_address', parsed.sid2_address)
        update_hist('sid3_address', parsed.sid3_address)
        update_hist('sid_count', parsed.sid_count)
        update_hist('contains_basic', parsed.contains_basic())

print("\nHistograms:")
max_hist_entries_to_display = 20
for category, hist in histograms.items():
    hist = dict(sorted(hist.items(), key=operator.itemgetter(1), reverse=True))

    if len(hist) > max_hist_entries_to_display:
        trunc_note = " (%d most common)" % max_hist_entries_to_display
        hist = dict(itertools.islice(hist.items(), max_hist_entries_to_display))
    else:
        trunc_note = ""

    lmax = max(len(str(v)) for v in hist)

    print(f"\n{category}{trunc_note}:")
    print('  ' + '\n  '.join(f'{str(value):>{lmax}}: {hist[value]}' for value in hist))

'''
Histograms:

magic_id:
  b'PSID': 49119
  b'RSID': 3208

version:
  2: 52121
  3: 189
  4: 17

data_offset:
  124: 52327

load_address (20 most common):
   4096: 28028
   6144: 2355
  40960: 2174
  32768: 825
  49152: 804
   3840: 733
  57344: 692
   2049: 672
  30080: 635
  16384: 629
   4095: 620
  24576: 605
   8192: 566
  36864: 498
  20480: 349
   4089: 349
   4086: 346
  12288: 327
   2048: 307
  28672: 286

init_address (20 most common):
   4096: 25228
   6144: 2292
  49152: 1962
   4168: 1772
  30080: 632
   4095: 598
  32768: 543
  24576: 497
      0: 495
  57344: 433
  49224: 389
  16384: 365
   4086: 344
   8192: 334
   6378: 287
  36864: 257
  40960: 239
  52180: 234
   4099: 230
  20480: 226

play_address (20 most common):
   4099: 25668
      0: 3311
   6150: 2516
   4129: 1777
  49184: 1441
   4102: 1023
  30087: 630
  32771: 496
  50293: 485
  49185: 391
  57347: 375
   4096: 359
  24582: 335
   5354: 287
  16387: 255
  36867: 225
  40963: 213
   8454: 181
  22362: 181
  49155: 169

num_subtunes (20 most common):
   1: 48213
   2: 1070
   3: 694
   4: 505
   5: 385
   6: 268
   7: 191
   8: 167
   9: 124
  11: 85
  10: 81
  12: 68
  13: 57
  14: 46
  18: 44
  16: 35
  15: 33
  20: 29
  17: 27
  21: 20

start_song (20 most common):
   1: 51764
   2: 226
   3: 105
   4: 60
   5: 50
   6: 27
   7: 26
   9: 16
   8: 14
  11: 7
  10: 5
  13: 4
  16: 3
  12: 3
  17: 3
  19: 2
  15: 2
  26: 2
  14: 2
  20: 1

speed (20 most common):
           0: 46549
           1: 5390
           3: 106
           7: 53
          15: 39
          31: 34
         127: 17
          63: 17
        4095: 12
         255: 12
        2047: 11
        1023: 9
        8191: 8
         511: 8
  4294967295: 5
           2: 5
      131071: 4
      524287: 4
       32767: 4
           6: 4

compute sid player:
  False: 52327

flag_1:
  False: 51832
   True: 495

clock:
           PAL: 46309
       Unknown: 3468
          NTSC: 2528
  NTSC and PAL: 22

sid_model:
              MOS6581: 22146
              MOS8580: 19660
              Unknown: 9895
  MOS6581 and MOS8580: 626

sid2_model:
              MOS6581: 22146
              MOS8580: 19660
              Unknown: 9895
  MOS6581 and MOS8580: 626

sid3_model:
              MOS6581: 22146
              MOS8580: 19660
              Unknown: 9895
  MOS6581 and MOS8580: 626

start_page (20 most common):
    0: 46376
    8: 2941
    4: 1177
   32: 72
   89: 65
   64: 56
   31: 42
   30: 41
   11: 38
   33: 36
  192: 32
   81: 31
   27: 30
   29: 30
   16: 30
   65: 28
   70: 25
   34: 25
   61: 24
   73: 24

page_length (20 most common):
    0: 46376
  152: 1658
  151: 212
  120: 210
   76: 191
  121: 167
   41: 115
  136: 89
    4: 86
  119: 80
  156: 75
   87: 71
   12: 68
   56: 67
  125: 65
   49: 64
   39: 63
  104: 60
  128: 57
   96: 56

sid2_address:
      0: 52121
  54304: 125
  54528: 65
  56832: 13
  54432: 1
  54560: 1
  54688: 1

sid3_address:
      0: 52310
  54336: 13
  54784: 2
  57088: 2

sid_count:
  1: 52121
  2: 189
  3: 17

init_sets_irq:
  RSID: 3208
  PSID: 103

init_no_irq:
  PSID: 49016

contains_basic:
  False: 51832
   True: 495
'''
