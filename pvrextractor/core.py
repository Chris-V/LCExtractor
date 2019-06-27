#
# core.py
#
# Copyright (C) 2017 levic92
#
# Basic plugin template created by:
# Copyright (C) 2008 Martijn Voncken <mvoncken@gmail.com>
# Copyright (C) 2007-2009 Andrew Resch <andrewresch@gmail.com>
#
# Deluge is free software.
#
# You may redistribute it and/or modify it under the terms of the
# GNU General Public License, as published by the Free Software
# Foundation; either version 3 of the License, or (at your option)
# any later version.
#
# deluge is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with deluge.    If not, write to:
# 	The Free Software Foundation, Inc.,
# 	51 Franklin Street, Fifth Floor
# 	Boston, MA  02110-1301, USA.
#
#    In addition, as a special exception, the copyright holders give
#    permission to link the code of portions of this program with the OpenSSL
#    library.
#    You must obey the GNU General Public License in all respects for all of
#    the code used other than OpenSSL. If you modify file(s) with this
#    exception, you may extend this exception to your version of the file(s),
#    but you are not obligated to do so. If you do not wish to do so, delete
#    this exception statement from your version. If you delete this exception
#    statement from all source files in the program, then also delete it here.
#
#

from __future__ import unicode_literals

import errno
import logging
import os

import deluge.component as component
import deluge.configmanager
from deluge.common import windows_check
from deluge.core.rpcserver import export
from deluge.plugins.pluginbase import CorePluginBase
from twisted.internet.utils import getProcessOutputAndValue
from twisted.python.procutils import which

CONFIG_EXTRACT_PATH = 'extract_path'
CONFIG_SUPPORTED_LABELS = 'supported_labels'
CONFIG_NAME_FOLDER = 'use_name_folder'
CONFIG_IN_PLACE_EXTRACT = 'in_place_extraction'
CONFIG_PVR_SUPPORT = 'sonarr_radarr_support'

DEFAULT_PREFS = {
    CONFIG_EXTRACT_PATH: '',
    CONFIG_SUPPORTED_LABELS: '',
    CONFIG_NAME_FOLDER: True,
    CONFIG_IN_PLACE_EXTRACT: True,
    CONFIG_PVR_SUPPORT: True,
}

EXTRACT_COMMANDS = {}

log = logging.getLogger(__name__)

if windows_check():
    win_7z_exes = [
        '7z.exe',
        'C:\\Program Files\\7-Zip\\7z.exe',
        'C:\\Program Files (x86)\\7-Zip\\7z.exe',
    ]

    try:
        import winreg
    except ImportError:
        import _winreg as winreg  # For Python 2.

    try:
        hkey = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Software\\7-Zip')
    except WindowsError:
        pass
    else:
        win_7z_path = os.path.join(winreg.QueryValueEx(hkey, 'Path')[0],
                                   '7z.exe')
        winreg.CloseKey(hkey)
        win_7z_exes.insert(1, win_7z_path)

    switch_7z = 'x -y'
    ## Future suport:
    ## 7-zip cannot extract tar.* with single command.
    #    ".tar.gz", ".tgz",
    #    ".tar.bz2", ".tbz",
    #    ".tar.lzma", ".tlz",
    #    ".tar.xz", ".txz",
    exts_7z = ['.rar', '.zip', '.tar', '.7z', '.xz', '.lzma']

    for win_7z_exe in win_7z_exes:
        if which(win_7z_exe):
            EXTRACT_COMMANDS = dict.fromkeys(exts_7z, [win_7z_exe, switch_7z])
            break

else:
    required_commands = [
        'unrar',
        'unzip',
        'tar',
        'unxz',
        'unlzma',
        '7zr',
        'bunzip2',
    ]
    # Possible future support:
    # gunzip: gz (cmd will delete original archive)
    # the following do not extract to dest dir
    # ".xz": ["xz", "-d --keep"],
    # ".lzma": ["xz", "-d --format=lzma --keep"],
    # ".bz2": ["bzip2", "-d --keep"],

    EXTRACT_COMMANDS = {
        '.rar': ['unrar', 'x -or -y'],
        '.tar': ['tar', '-xf'],
        '.zip': ['unzip', ''],
        '.tar.gz': ['tar', '-xzf'],
        '.tgz': ['tar', '-xzf'],
        '.tar.bz2': ['tar', '-xjf'],
        '.tbz': ['tar', '-xjf'],
        '.tar.lzma': ['tar', '--lzma -xf'],
        '.tlz': ['tar', '--lzma -xf'],
        '.tar.xz': ['tar', '--xz -xf'],
        '.txz': ['tar', '--xz -xf'],
        '.7z': ['7zr', 'x'],
    }

    # Test command exists and if not, remove.
    for required_command in required_commands:
        if not which(required_command):
            for k, v in list(EXTRACT_COMMANDS.items()):
                if required_command in v[0]:
                    log.warning(
                        '%s not found, disabling support for %s',
                        required_command, k
                    )
                    del EXTRACT_COMMANDS[k]

if not EXTRACT_COMMANDS:
    raise Exception(
        'PVR EXTRACTOR: No archive extracting programs found, plugin will be disabled'
    )


class Core(CorePluginBase):
    def enable(self):
        self.config = deluge.configmanager.ConfigManager(
            'pvr_extractor.conf', DEFAULT_PREFS
        )
        if not self.config[CONFIG_EXTRACT_PATH]:
            self.config[CONFIG_EXTRACT_PATH] = \
                deluge.configmanager.ConfigManager(
                    'core.conf'
                )['download_location']

        self.supported_labels = list(filter(None, map(
            lambda i: i.strip(),
            self.config[CONFIG_SUPPORTED_LABELS].split(',')
        )))

        component.get('EventManager').register_event_handler(
            'TorrentFinishedEvent', self._on_torrent_finished
        )

    def disable(self):
        component.get('EventManager').deregister_event_handler(
            'TorrentFinishedEvent', self._on_torrent_finished
        )

    def update(self):
        pass

    def _on_torrent_finished(self, torrent_id):
        """
        This is called when a torrent finishes and checks if any files need
        extraction.
        """
        torrent = component.get('TorrentManager').torrents[torrent_id]
        torrent_name = torrent.get_status(['name'])['name']
        torrent_label = component.get('CorePluginManager').get_status(
            torrent_id, ['label']
        )['label']

        if self.config[CONFIG_SUPPORTED_LABELS] \
            and torrent_label not in self.config[CONFIG_SUPPORTED_LABELS]:
            log.info(
                'Label %s is not in supported list. Skip extraction: %s',
                torrent_label, torrent_name
            )
            return

        if self.config[CONFIG_PVR_SUPPORT]:
            log.info(
                'Prevent PVR from processing download. Set is_finished to false: %s',
                torrent_name
            )
            torrent.is_finished = False

        extraction_count = self._extract_torrent(torrent)

        if self.config[CONFIG_PVR_SUPPORT] and extraction_count[0] == 0:
            log.info(
                'Nothing to extract. Set is_finished to true: %s',
                torrent_name
            )
            torrent.is_finished = True

    def _extract_torrent(self, torrent):
        torrent_status = torrent.get_status(['download_location', 'name'])
        torrent_name = torrent_status['name']
        torrent_location = torrent_status['download_location']

        # keep track of total extraction jobs... store in list so it is mutable
        # index 0 = total, index 1 = completed
        extraction_count = [0, 0]
        files = torrent.get_files()

        for file in files:
            file_path = file['path']

            command = self._find_extract_command(file_path)
            if command is None:
                continue

            file_path = os.path.join(
                torrent_location,
                os.path.normpath(file_path)
            )
            extract_path = self._find_destination_path(
                torrent_name,
                torrent_location,
            )

            if extract_path is None:
                break

            def _on_extract(result, torrent, file_path, pvr_support, counts):
                counts[1] += 1
                log.debug(
                    'Extraction count total %d, complete %d',
                    counts[0],
                    counts[1]
                )

                if pvr_support and counts[0] == counts[1]:
                    log.info(
                        'Setting is_finished to true: %s',
                        torrent.torrent_id
                    )
                    torrent.is_finished = True

                if not result[2]:
                    log.info(
                        'Extract successful: %s (%s)',
                        file_path,
                        torrent.torrent_id
                    )
                else:
                    log.error(
                        'Extract failed: %s (%s), %s',
                        file_path,
                        torrent.torrent_id,
                        result[1]
                    )

            # increment extraction_count
            extraction_count[0] += 1
            log.debug(
                'Extraction count total %d, complete %d',
                extraction_count[0],
                extraction_count[1],
            )

            # Run the command and add callback.
            log.debug(
                'Extracting %s from %s with %s %s to %s',
                file_path,
                torrent.id,
                command[0],
                command[1],
                extract_path,
            )
            d = getProcessOutputAndValue(
                command[0],
                command[1].split() + [str(file_path)],
                os.environ,
                str(extract_path)
            )
            d.addCallback(
                _on_extract,
                torrent,
                file_path,
                self.config[CONFIG_PVR_SUPPORT],
                extraction_count,
            )

        return extraction_count

    def _find_extract_command(self, file_path):
        file_root, file_ext = os.path.splitext(file_path)
        file_ext_sec = os.path.splitext(file_root)[1]

        if file_ext_sec and file_ext_sec + file_ext in EXTRACT_COMMANDS:
            return EXTRACT_COMMANDS[file_ext_sec + file_ext]
        elif file_ext not in EXTRACT_COMMANDS or file_ext_sec == '.tar':
            log.debug(
                'EXTRACTOR: Can\'t extract file with unknown file type: %s',
                file_path)
            return None
        elif file_ext == ".rar" and "part" in file_ext_sec:
            part_num = file_ext_sec.split("part")[1]
            if part_num.isdigit() and int(part_num) != 1:
                log.debug('Skipping remaining multi-part rar files: %s',
                          file_path)
                return None

    def _find_destination_path(self, torrent_name, torrent_location):
        extract_path = os.path.normpath(self.config[CONFIG_EXTRACT_PATH])
        dest_path = os.path.join(extract_path, torrent_name)

        # Override destination if in_place_extraction is set
        if self.config[CONFIG_IN_PLACE_EXTRACT]:
            extract_path = torrent_location
            dest_path = os.path.join(extract_path, torrent_name)

        # make sure path does not exist or parent directory matches the name
        # occasionally name is actually just the file
        if self.config[CONFIG_NAME_FOLDER] and (
            not os.path.exists(dest_path)
            or os.path.isdir(dest_path)
        ):
            extract_path = dest_path

        try:
            os.makedirs(extract_path)
        except OSError as ex:
            if not (ex.errno == errno.EEXIST and os.path.isdir(extract_path)):
                log.error(
                    'EXTRACTOR: Error creating destination folder: %s',
                    ex
                )
                return None

        return extract_path

    @export
    def set_config(self, config):
        """Sets the config dictionary."""
        for key in config:
            self.config[key] = config[key]
        self.config.save()

    @export
    def get_config(self):
        """Returns the config dictionary."""
        return self.config.config
