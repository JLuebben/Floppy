#!python3

import sys
import glob
import os.path
# import subprocess

from subprocess import Popen, PIPE, TimeoutExpired



if __name__ == '__main__':
    wd = sys.argv[-1]
    report = []
    for file in glob.glob(wd):
        # x = subprocess.call(, shell=True)
        _run = os.path.join(os.path.dirname(__file__),'Floppy.py')
        try:
            p = Popen(['python.exe', _run, '--test', '{}'.format(file)], stdin=PIPE, stdout=PIPE, stderr=PIPE)
        except FileNotFoundError:
            try:
                p = Popen(['python3', _run, '--test', '{}'.format(file)], stdin=PIPE, stdout=PIPE, stderr=PIPE)
            except FileNotFoundError:
                p = Popen(['python', _run, '--test', '{}'.format(file)], stdin=PIPE, stdout=PIPE, stderr=PIPE)
        try:
            output, err = p.communicate("", timeout=20)
        except TimeoutExpired:
            report.append((file, (1, 'Unkown Error')))
        else:
            rc = p.returncode
            try:
                r = eval(err.decode())
            except:
                r = err.decode()
            report.append((file, r))
        # for line in err.readlines():
        #     print(line)
    print('Test Result:')
    for f, r in report:
        print('   {1:6} -- {0:50} {2}'.format(f, 'Passed' if not r[0] else 'Failed', r[1] if r[0] else ''))

