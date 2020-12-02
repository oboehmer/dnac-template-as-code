#!/usr/bin/env python
#
# Parse Robotframework's output.xml in a pipeline to extract test results
# for notification
#
import sys
import xml.etree.ElementTree as ET
from utils import update_results_json


def extract_test_results(xmlfile):

    root = ET.parse(xmlfile).getroot()
    stats = {}
    for elem in root.findall('./statistics/total/stat'):
        stats[elem.text] = ', '.join(['{}: {}'.format(k, v) for k, v in elem.attrib.items()])

    return stats


if __name__ == '__main__':

    if len(sys.argv) != 3:
        print('Usage: {} xml-file json-file'.format(sys.argv[0]))
        sys.exit(1)

    try:
        results = extract_test_results(sys.argv[1])
        update_results_json(filename=sys.argv[2], message='Robot Test Results', stats=results)
    except FileNotFoundError:
        print('ignored file not found error')

    sys.exit(0)
