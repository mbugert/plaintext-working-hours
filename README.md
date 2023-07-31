# Parser for Plaintext Logs of Working Hours

Given plaintext logs like this:
```
13.01.2023   09:36 - 17:32
    -10min KK

16.01.2023  08:13 - 19:05   WFH
    minus 13:55 - 14:45 internet technician
17.01.2023  09:30 - 18:08
18.01.2023  08:51 - 17:10
19.01.2023  08:07 - 17:36  WFH
    minus 09:10 - 09:26 sidequest
    minus 11:40 - 11:47 another one
20.01.2023  07:58 - 17:00       WFH
    -30

23.01.2023 07:50 - 17:16
    -11min
    17:55 - 18:43
24.01.2023 08:30 - 12:40
    plus 14:00 - 18:03 WFH
25.01.2023 vacation
26.01.2023 sick
```

The script in this repo parses the log to produce a report like this:
```commandline
❯ python3 parse.py --delta --working-hours 8 --daily-break-hours 0.5 sample.md
2023-01-13      -0.73
2023-01-16      +0.80
2023-01-17      +0.93
2023-01-18      +0.75
2023-01-19      +1.35
2023-01-20      +1.38
2023-01-23      +2.93
2023-01-24      +2.65
```
Or this:
```commandline
❯ python3 parse.py --count sample.md
2023:
in office       4
WFH     4
vacation        1
sick    1
total   10
```

Or just CSV:
```commandline
❯ python3 parse.py sample.md --csv
date,seconds,description
2023-01-13,28560.0,
2023-01-13,-600.0,KK
2023-01-16,39120.0,WFH
2023-01-16,-3000.0,internet technician
2023-01-17,31080.0,
2023-01-18,29940.0,
2023-01-19,34140.0,WFH
...
```

## Setup
1. Have python>=3.10 
2. Clone the repo, create and activate venv
3. `pip install -r requirements.txt`

## Usage
```commandline
❯ python3 parse.py --help
usage: parse.py [-h] [--csv | -d | -c] [-w WORKING_HOURS] [-b DAILY_BREAK_HOURS] filename

Creates reports from plaintext logs of working hours.

positional arguments:
  filename              Plaintext file with working times

options:
  -h, --help            show this help message and exit
  --csv                 Parse file and print CSV
  -d, --delta           Print cumulative delta (default action)
  -c, --count           Count in-office, WFH, etc. days
  -w WORKING_HOURS, --working-hours WORKING_HOURS
                        Working hours per day (default: 8.0), only used with the '--delta' option.
  -b DAILY_BREAK_HOURS, --daily-break-hours DAILY_BREAK_HOURS
                        Hours of break to subtract from each working day (default: 0.5), only used with the '--delta' option.
```

Happy working (and logging)! 🎉
