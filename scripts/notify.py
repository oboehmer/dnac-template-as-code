#!/usr/bin/env python
import argparse
import os
import sys

import yaml
from attrdict import AttrDict
from webexteamssdk import WebexTeamsAPI


class Notify(object):
    '''
    send webex notification to persons or teams
    '''

    def __init__(self, config_file=None):
        # read config files
        if config_file is None:
            config_file = os.path.join(os.path.dirname(__file__), 'config.yaml')
        with open(config_file) as fd:
            self.config = AttrDict(yaml.safe_load(fd.read()))

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

    def notify(self, message, roomid=None, persons=[]):
        '''
        send notification to rooms and/or persons identified in the config file
        '''

        if roomid is None:
            if hasattr(self.config.notify, 'room_id'):
                roomid = self.config.notify.room_id
            else:
                roomid = None

        if not len(persons):
            if hasattr(self.config.notify, 'persons'):
                p = self.config.notify.persons
                if isinstance(p, str):
                    persons = [p]
                else:
                    persons = p

        if roomid:
            self.api.messages.create(markdown=message, roomId=roomid)
        for p in persons:
            if '@' in p:
                self.api.messages.create(markdown=message, toPersonEmail=p)
            else:
                self.api.messages.create(markdown=message, toPersonId=p)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Notify')
    parser.add_argument('--room', help='WebexTeams room id to send to')
    parser.add_argument('--person', help='person ID or email (multiple values can be specified, comma-separated')
    parser.add_argument('--config', help='config file to use')
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
    notif.notify(' '.join(args.message), roomid=args.room, persons=persons)
