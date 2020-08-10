# Download additional resources that could be used in testing / demonstrations
# that don't belong in the github code base

import os
import time
import requests
from random import uniform

from chiptunesak.constants import project_to_absolute_path

SKIP_IF_EXISTS = True
last_site = None


class ResourceFile:
    def __init__(self, remote_url, local_path, local_name=None):
        self.remote_url = remote_url
        self.local_path = local_path
        self.local_name = local_name
        if local_name is None:  # if filename not specified, use filename from url
            self.local_name = remote_url.split('/')[-1]


def manage_resources(resources):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:75.0) Gecko/20100101 Firefox/75.0'
    }

    for resource in resources:
        local_path = project_to_absolute_path(resource.local_path)

        # pathlib would have been better (can build full dir paths), but didn't work for me
        # pathlib.Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        # TODO: this approach assumes parent dir exists.  Make a nested directory creator routine
        # and use it here.
        os.makedirs(local_path, exist_ok=True)

        local_file = os.path.normpath(os.path.join(local_path, resource.local_name))

        if os.path.exists(local_file):
            if not os.path.isfile(local_file):
                raise Exception('Error: not expecting "%s" to not be a file' % (local_file))
            if SKIP_IF_EXISTS:
                print('"%s" exists, skipping' % (local_file))
                continue
            else:
                print('Will overwrite "%s"' % (local_file))

        print("%s -> %s" % (resource.remote_url, local_file))
        try:
            response = requests.get(resource.remote_url, headers=headers)
        except requests.exceptions.RequestException as e:
            print('Unable to download file at "%s", due to exception "%s"' % (resource.remote_url, e))
            continue

        content = response.content

        if b'<html' in content.lower()[0:200]:
            print('Warning: "%s" might merely be HTML saying the equivalent of "no botz allowed"' % (local_file))

        with open(local_file, 'wb') as out_file:
            out_file.write(content)

        time.sleep(uniform(1.5, 2.8))  # be friendly to web sites
        print()


def main():
    resources = []

    # C64 ROMs

    resources.append(ResourceFile(
        'http://www.zimmers.net/anonftp/pub/cbm/firmware/computers/c64/kernal.901227-03.bin',
        'res',
        'c64kernal.bin'
    ))

    resources.append(ResourceFile(
        'http://www.zimmers.net/anonftp/pub/cbm/firmware/computers/c64/basic.901226-01.bin',
        'res',
        'c64basic.bin'
    ))

    resources.append(ResourceFile(
        'http://www.zimmers.net/anonftp/pub/cbm/firmware/computers/c64/characters.901225-01.bin',
        'res',
        'c64char.bin'
    ))

    # C64 music examples

    # An HVSC mirror:
    an_hvsc_mirror = 'https://www.sannic.nl/hvsc/C64Music/MUSICIANS'
    # Note above URL base works for downloading, but not HTML navigating.
    # The below URL works for navigating, but not for downloading:
    # https://www.sannic.nl/hvsc/?dir=C64Music/MUSICIANS

    download_dir = 'examples/data/sid'

    resources.append(ResourceFile(
        an_hvsc_mirror + '/B/Boles_Howard/Dragonworld.sid', download_dir))

    resources.append(ResourceFile(
        an_hvsc_mirror + '/D/Daglish_Ben/Butcher_Hill.sid', download_dir))

    resources.append(ResourceFile(
        an_hvsc_mirror + '/D/Dunbar_Tommy/Archon.sid', download_dir))

    resources.append(ResourceFile(
        an_hvsc_mirror + '/F/Fulton_Douglas/Skyfox.sid', download_dir))

    resources.append(ResourceFile(
        an_hvsc_mirror + '/L/Lieblich_Russell/Master_of_the_Lamps_PAL.sid', download_dir))

    resources.append(ResourceFile(
        an_hvsc_mirror + '/N/Norman_Paul/Super_Huey.sid', download_dir))

    resources.append(ResourceFile(
        an_hvsc_mirror + '/W/Warhol_Dave/Pool_of_Radiance.sid', download_dir))

    resources.append(ResourceFile(
        'https://www.sannic.nl/hvsc/C64Music/DEMOS/M-R/Nitro.sid', download_dir))

    # Apple ][ music examples

    download_dir = 'examples/data/appleii_u4'

    resources.append(ResourceFile(
        'http://youdzone.com/testData/appleii/u4/must', download_dir))

    resources.append(ResourceFile(
        'http://youdzone.com/testData/appleii/u4/muso', download_dir))

    resources.append(ResourceFile(
        'http://youdzone.com/testData/appleii/u4/musd', download_dir))

    resources.append(ResourceFile(
        'http://youdzone.com/testData/appleii/u4/musc', download_dir))

    resources.append(ResourceFile(
        'http://youdzone.com/testData/appleii/u4/musb', download_dir))

    # MS-DOS music examples

    resources.append(ResourceFile(
        'https://www.midiarchive.co.uk/downloadfile/Games/Monkey%20Island%201/Monkey%20Island%201%20-%20The%20Ghost%20Pirate%20Lechuck%20Ver%203.mid',
        'examples/data/lechuck',
        'MonkeyIsland_LechuckTheme.mid'
    ))

    resources.append(ResourceFile(
        'http://youdzone.com/testData/msdos/betrayalKrondorMercantile.mid',
        'examples/data/mercantile'))

    manage_resources(resources)

    print("\nDone")


if __name__ == "__main__":
    main()
