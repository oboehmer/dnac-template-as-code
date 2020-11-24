#!/usr/bin/env python
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

    def notify(self, message, roomid=None, persons=[], result_json=None):
        '''
        send notification to rooms and/or persons identified in the config file
        '''

        if result_json:
            for f in result_json:
                try:
                    with open(f) as fd:
                        results = json.load(fd)
                    message += '\n'
                    for k, v in results.items():
                        message += '- {}: {}\n'.format(k, v)
                except Exception as e:
                    print('Exception ignored while processing results: {}'.format(str(e)))
                    pass

        args_given = roomid or len(persons) > 0
        if not args_given:
            if hasattr(self.config.notify, 'room_id'):
                roomid = self.config.notify.room_id

            if hasattr(self.config.notify, 'persons'):
                p = self.config.notify.persons
                if isinstance(p, str):
                    persons = [p]
                else:
                    persons = p

        if roomid:
            self.api.messages.create(markdown=message, text=message, roomId=roomid)
        for p in persons:
            if '@' in p:
                self.api.messages.create(markdown=message, text=message, toPersonEmail=p)
            else:
                self.api.messages.create(markdown=message, text=message, toPersonId=p)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Notify')
    parser.add_argument('--room', help='WebexTeams room id to send to')
    parser.add_argument('--person', help='person ID or email (multiple values can be specified, comma-separated')
    parser.add_argument('--config', help='config file to use')
    parser.add_argument('--results', action='append', help='load results from json file(s), use multiple times for multiple files (default: no result)')
    parser.add_argument('message', nargs=argparse.REMAINDER, help='message to be sent')
    args = parser.parse_args()

    if args.person:
        persons = args.person.split(',')
    else:
        persons = []
    if not len(args.message):
        print('no message provided')
        sys.exit(1)

    notif = Notify(config_file=args.config)
    notif.notify(' '.join(args.message), roomid=args.room, persons=persons, result_json=args.results)
