#!/usr/bin/env python
#
# Copyright (c) 2019 Cisco and/or its affiliates.
# This software is licensed to you under the terms of the Cisco Sample
# Code License, Version 1.0 (the "License"). You may obtain a copy of the
# License at
#                https://developer.cisco.com/docs/licenses
# All use of the material herein must be in accordance with the terms of
# the License. All rights not expressly granted by the License are
# reserved. Unless required by applicable law or agreed to separately in
# writing, software distributed under the License is distributed on an "AS
# IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
# or implied.

import argparse
import json
import os
import sys

from webexteamssdk import WebexTeamsAPI
from utils import read_config


class Notify(object):
    '''
    send webex notification to persons or teams
    '''

    def __init__(self, config_file=None):
        # read config files
        if config_file is None:
            config_file = os.path.join(os.path.dirname(__file__), 'config.yaml')
        self.config = read_config(config_file)

        if not hasattr(self.config, 'notify'):
            raise ValueError('missing notify config section')

        if hasattr(self.config.notify, 'token'):
            token = self.config.notify.token
        else:
            token = os.environ.get('WEBEX_API_NOTIFICATION_TOKEN')
        if not token:
            raise ValueError('Error, no token configured or present in $WEBEX_API_NOTIFICATION_TOKEN environment')

        # login to Webex
        self.api = WebexTeamsAPI(access_token=token)

    def notify(self, message, rooms=None, persons=None, result_json=None, attach=None):
        '''
        send notification to rooms and/or persons identified in the config file
        '''

        if result_json:
            message += '\n'
            for f in result_json:
                try:
                    with open(f) as fd:
                        results = json.load(fd)
                    message += '\n'
                    for k, v in results.items():
                        message += '- {}: '.format(k)
                        print(k, v)
                        if isinstance(v, dict):
                            message += ', '.join(['{}: {}'.format(k1, v1) for k1, v1 in v.items()])
                        elif isinstance(v, list):
                            message += ', '.join([str(i) for i in v])
                        else:
                            message += str(v)
                        message += '\n'
                except Exception as e:
                    print('Exception ignored while processing results: {}'.format(str(e)))
                    pass

        if rooms is None:
            rooms = []
        if persons is None:
            persons = []
        args_given = len(rooms) or len(persons)
        if not args_given:
            if hasattr(self.config.notify, 'room_ids'):
                r = self.config.notify.room_ids
                if isinstance(r, str):
                    rooms = [r]
                else:
                    rooms = r

            if hasattr(self.config.notify, 'persons'):
                p = self.config.notify.persons
                if isinstance(p, str):
                    persons = [p]
                else:
                    persons = p

        recepients = []
        for r in rooms:
            recepients.append({'roomId': r})

        for p in persons:
            if '@' in p:
                recepients.append({'toPersonEmail': p})
            else:
                recepients.append({'toPersonId': p})

        if len(recepients) == 0:
            print('No recepients found or specified')
            return

        if not attach:
            attach = []

        for r in recepients:
            # print('sending to {}, files={}'.format(r, files))
            result = self.api.messages.create(markdown=message, text=message, **r)
            # attach more files via replies to the message
            for file in attach:
                if not os.path.exists(file):
                    print('File {} doesn\'t exist, ignoring error'.format(file))
                    continue

                try:
                    self.api.messages.create(text='', parentId=result.id, files=[file], **r)
                except Exception as e:
                    print('Exception ignored while sending file {}: {}'.format(file, str(e)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Notify')
    parser.add_argument('--room', help='WebexTeams room id to send to (multiple values can be specified, comma-separated)')
    parser.add_argument('--person', help='person ID or email (multiple values can be specified, comma-separated)')
    parser.add_argument('--config', help='config file to use')
    parser.add_argument('--attach', action='append', help='file to attach (repeat to attach more files).')
    parser.add_argument('--results', action='append', help='load results from json file(s), use multiple times for multiple files (default: no result)')
    parser.add_argument('message', nargs=argparse.REMAINDER, help='message to be sent')
    args = parser.parse_args()

    if args.person:
        persons = args.person.split(',')
    else:
        persons = []
    if args.room:
        rooms = args.person.split(',')
    else:
        rooms = []
    if not len(args.message):
        print('no message provided')
        sys.exit(1)

    notif = Notify(config_file=args.config)
    notif.notify(' '.join(args.message), rooms=rooms, persons=persons, result_json=args.results, attach=args.attach)
