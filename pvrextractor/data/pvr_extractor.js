/*!
 * pvr_extractor.js
 *
 * This file is part of Deluge and is licensed under GNU General Public License 3.0, or later, with
 * the additional special exception to link portions of this program with the OpenSSL library.
 * See LICENSE for more details.
 *
 */

Ext.ns('Deluge.ux.preferences');

/**
 * @class Deluge.ux.preferences.PVRExtractorPage
 * @extends Ext.Panel
 */
Deluge.ux.preferences.PVRExtractorPage = Ext.extend(Ext.Panel, {

    title: _('PVR Extractor'),
    layout: 'fit',
    header: false,
    border: false,

    configLoaded: false,
    configKeys: {
        extractPath: 'extract_path',
        supportedLabels: 'supported_labels',
        nameFolder: 'use_name_folder',
        inPlaceExtract: 'in_place_extraction',
        pvrSupport: 'sonarr_radarr_support',
    },

    initComponent: function () {
        Deluge.ux.preferences.PVRExtractorPage.superclass.initComponent.call(this);

        this.form = this.add({
            xtype: 'form',
            layout: 'form',
            border: false,
            autoHeight: true,
        });

        fieldset = this.form.add({
            xtype: 'fieldset',
            border: false,
            title: '',
            autoHeight: true,
            labelAlign: 'top',
            labelWidth: 80,
            defaultType: 'textfield',
        });

        this.extract_path = fieldset.add({
            fieldLabel: _('Extract to:'),
            labelSeparator: '',
            name: 'extract_path',
            width: '97%',
        });

        this.supported_labels = fieldset.add({
            fieldLabel: _('Supported labels:'),
            labelSeparator: '',
            name: 'supported_labels',
            width: '97%',
        });

        this.use_name_folder = fieldset.add({
            xtype: 'checkbox',
            name: 'use_name_folder',
            height: 22,
            hideLabel: true,
            boxLabel: _('Create torrent name sub-folder'),
        });

        this.in_place_extraction = fieldset.add({
            xtype: 'checkbox',
            name: 'in_place_extraction',
            height: 22,
            hideLabel: true,
            boxLabel: _('Extract torrent in-place'),
        });

        this.sonarr_radarr_support = fieldset.add({
            xtype: 'checkbox',
            name: 'sonarr_radarr_support',
            height: 22,
            hideLabel: true,
            boxLabel: _('Enable support for Sonarr, Radarr'),
        });

        this.on('show', this.updateConfig, this);
    },

    onApply: function () {
        // Only apply the settings if we've previously loaded them (or else we end up resetting the config!).
        if (this.configLoaded) {
            deluge.client.pvrextractor.set_config({
                [this.configKeys.extractPath]: this.extract_path.getValue(),
                [this.configKeys.supportedLabels]: this.supported_labels.getValue(),
                [this.configKeys.nameFolder]: this.use_name_folder.getValue(),
                [this.configKeys.inPlaceExtract]: this.in_place_extraction.getValue(),
                [this.configKeys.pvrSupport]: this.sonarr_radarr_support.getValue(),
            });
        }
    },

    onOk: function () {
        this.onApply();
    },

    updateConfig: function () {
        deluge.client.pvrextractor.get_config({
            success: function (config) {
                this.extract_path.setValue(config[this.configKeys.extractPath]);
                this.supported_labels.setValue(config[this.configKeys.supportedLabels]);
                this.use_name_folder.setValue(config[this.configKeys.nameFolder]);
                this.in_place_extraction.setValue(config[this.configKeys.inPlaceExtract]);
                this.sonarr_radarr_support.setValue(config[this.configKeys.pvrSupport]);
                this.configLoaded = true;
            },
            scope: this,
        });
    },
});


Deluge.plugins.PVRExtractorPlugin = Ext.extend(Deluge.Plugin, {
    name: 'PVR Extractor',

    onDisable: function () {
        deluge.preferences.removePage(this.prefsPage);
    },

    onEnable: function () {
        this.prefsPage = deluge.preferences.addPage(new Deluge.ux.preferences.PVRExtractorPage());
    },
});
Deluge.registerPlugin('PVRExtractor', Deluge.plugins.PVRExtractorPlugin);
