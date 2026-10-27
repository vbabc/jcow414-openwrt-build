"use strict";
"require view";
"require fs";
"require ui";
"require poll";

var control = '/sys/bus/platform/devices/1fb60000.xmac/activation';

return view.extend({
    load: function() { return fs.read(control); },
    render: function(initial) {
        var state = E('pre', {}, initial);
        var refresh = function() {
            return fs.read(control).then(function(value) { state.textContent = value; });
        };
        var act = function(value) {
            return fs.write(control, value).then(refresh).catch(function(error) {
                ui.addNotification(null, E('p', {}, error.message || String(error)), 'error');
            });
        };
        poll.add(refresh, 2);
        return E('div', {}, [
            E('h2', {}, _('GPON activation RAM test')),
            E('p', {}, _('Configure and apply your GPON serial under OMCI General settings before starting. Enable the baseline OMCI agent there for OMCI responses. Keep an independent internet connection and UART available.')),
            E('p', {}, _('Start permits normal GPON registration and upstream transmission for at most 180 seconds. It does not configure an internet WAN. Stop disables transmission immediately. The test ends automatically and must be explicitly started again.')),
            state,
            E('button', { 'class': 'cbi-button cbi-button-action', 'click': ui.createHandlerFn(this, function() { return act('1'); }) }, _('Start 3-minute test')),
            ' ',
            E('button', { 'class': 'cbi-button cbi-button-negative', 'click': ui.createHandlerFn(this, function() { return act('0'); }) }, _('Stop test'))
        ]);
    },
    handleSaveApply: null,
    handleSave: null,
    handleReset: null
});
