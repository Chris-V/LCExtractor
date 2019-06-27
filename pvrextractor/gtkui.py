#
# gtkui.py
#
# Copyright (C) 2009 Andrew Resch <andrewresch@gmail.com>
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

import logging

import gi  # isort:skip (Required before Gtk import).

gi.require_version('Gtk', '3.0')  # NOQA: E402

# isort:imports-thirdparty
from gi.repository import Gtk

# isort:imports-firstparty
import deluge.component as component
from deluge.plugins.pluginbase import Gtk3PluginBase
from deluge.ui.client import client

# isort:imports-localfolder
from .common import get_resource

log = logging.getLogger(__name__)

PAGE_NAME = 'PVR Extractor'
CONFIG_EXTRACT_PATH = 'extract_path'
CONFIG_SUPPORTED_LABELS = 'supported_labels'
CONFIG_NAME_FOLDER = 'use_name_folder'
CONFIG_IN_PLACE_EXTRACT = 'in_place_extraction'
CONFIG_PVR_SUPPORT = 'sonarr_radarr_support'


class GtkUI(Gtk3PluginBase):
    def enable(self):
        self.builder = Gtk.Builder()
        self.builder.add_from_file(get_resource('pvr_extractor_prefs.ui'))

        component.get('Preferences').add_page(
            _(PAGE_NAME), self.builder.get_object('pvr_extractor_prefs_box')
        )
        component.get('PluginManager').register_hook(
            'on_apply_prefs', self.on_apply_prefs
        )
        component.get('PluginManager').register_hook(
            'on_show_prefs', self.on_show_prefs
        )
        self.on_show_prefs()

    def disable(self):
        component.get('Preferences').remove_page(_(PAGE_NAME))
        component.get('PluginManager').deregister_hook(
            'on_apply_prefs', self.on_apply_prefs
        )
        component.get('PluginManager').deregister_hook(
            'on_show_prefs', self.on_show_prefs
        )
        del self.builder

    def on_apply_prefs(self):
        log.debug('applying prefs for ' + PAGE_NAME)
        if client.is_localhost():
            path = self.get_folder_chooser_object().get_filename()
        else:
            path = self.get_entry_path_object().get_text()

        config = {
            CONFIG_EXTRACT_PATH: path,
            CONFIG_SUPPORTED_LABELS:
                self.get_supported_labels_object().get_text(),
            CONFIG_NAME_FOLDER:
                self.get_use_name_folder_object().get_active(),
            CONFIG_IN_PLACE_EXTRACT:
                self.get_in_place_extract_object().get_active(),
            CONFIG_PVR_SUPPORT:
                self.builder.get_pvr_support_object().get_active()
        }

        client.pvrextractor.set_config(config)

    def on_show_prefs(self):
        if client.is_localhost():
            self.get_folder_chooser_object().show()
            self.get_entry_path_object().hide()
        else:
            self.get_folder_chooser_object().hide()
            self.get_entry_path_object().show()

        def on_get_config(config):
            if client.is_localhost():
                self.get_folder_chooser_object().set_current_folder(
                    config[CONFIG_EXTRACT_PATH]
                )
            else:
                self.get_entry_path_object().set_text(
                    config[CONFIG_EXTRACT_PATH]
                )

            self.get_supported_labels_object().set_text(
                config[CONFIG_SUPPORTED_LABELS]
            )
            self.get_use_name_folder_object().set_active(
                config[CONFIG_NAME_FOLDER]
            )
            self.get_in_place_extract_object().set_active(
                config[CONFIG_IN_PLACE_EXTRACT]
            )
            config.get_pvr_support_object().set_active(
                config[CONFIG_PVR_SUPPORT]
            )

        client.pvrextractor.get_config().addCallback(on_get_config)

    def get_entry_path_object(self):
        return self.builder.get_object('entry_path')

    def get_folder_chooser_object(self):
        return self.builder.get_object('folderchooser_path')

    def get_supported_labels_object(self):
        return self.builder.get_object('txt_supported_labels')

    def get_use_name_folder_object(self):
        return self.builder.get_object('chk_use_name')

    def get_in_place_extract_object(self):
        return self.builder.get_object('chk_in_place_extraction')

    def get_pvr_support_object(self):
        return self.builder.get_object('chk_sonarr_radarr_support')
